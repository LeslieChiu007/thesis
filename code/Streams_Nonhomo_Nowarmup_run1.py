# Streams_Nonhomo_NoWarmup_run1_0814.py

import json
import os
import simpy
import numpy as np
import seaborn as sns
import itertools
import random
import math
import matplotlib.pyplot as plt

class PatientService:
    def __init__(self, env, num_beds, servicetime):
        self.env = env
        self.bed = simpy.Resource(env, num_beds)
        self.servicetime = servicetime

    def serve(self, patient):
        yield self.env.timeout(np.random.exponential(scale=self.servicetime))

def patient(env, name, ps, num_beds, proportion, stream_id, all_data):
    arrive = env.now
    if random.random() < proportion:
        all_data["leaving_patients"][stream_id].append((arrive, stream_id))
        return

    if arrive > all_data["warm_up_period"]:
        all_data["queue_lengths"][stream_id].append((env.now, len(ps.bed.queue)))
        all_data["num_patients"][stream_id].append((env.now, len(ps.bed.queue) + len(ps.bed.users)))

    with ps.bed.request() as request:
        yield request
        wait = env.now - arrive

        if arrive > all_data["warm_up_period"]:
            all_data["waiting_times"][stream_id].append(wait)
            if wait > 0:
                all_data["nonzero_waiting_times"][stream_id].append(wait)

        service_start = env.now
        yield env.process(ps.serve(name))
        service_time = env.now - service_start
        if arrive > all_data["warm_up_period"]:
            all_data["service_times"][stream_id].append(service_time)
            all_data["system_times"][stream_id].append(wait + service_time)
            all_data["total_service_time"][stream_id] += service_time
            all_data["utilization"][stream_id].append((env.now, all_data["total_service_time"][stream_id] / (num_beds * (env.now - all_data["warm_up_period"]))))
            all_data["served"][stream_id] += 1
            all_data["throughput"][stream_id].append((env.now, all_data["served"][stream_id] / (env.now - all_data["warm_up_period"])))

# for dynamic arrival rates
def setup(env, base_arrival_rate, service_rate, num_beds, proportion, stream_id, all_data):
    patientservice = PatientService(env, num_beds, 1/service_rate)
    patient_count = itertools.count()

    max_arrival_rate = base_arrival_rate * 1.1  # Maximum rate considering the sinusoidal fluctuation

    while True:
        interarrival_time = np.random.exponential(scale=1/max_arrival_rate)
        yield env.timeout(interarrival_time)
        t = env.now
        current_arrival_rate = base_arrival_rate + 0.1 * base_arrival_rate * math.sin(math.pi * t / 12)
        if random.random() <= current_arrival_rate / max_arrival_rate:
            env.process(patient(env, f'Patient {next(patient_count)}', patientservice, num_beds, proportion, stream_id, all_data))

def run_simulation(params, warm_up_period, sim_time):
    all_data = {key: {i: [] for i in range(1, 9)} for key in [
        'leaving_patients', 'queue_lengths', 'num_patients', 'waiting_times',
        'nonzero_waiting_times', 'service_times', 'system_times', 'utilization', 'throughput']}
    all_data['warm_up_period'] = warm_up_period
    all_data['total_service_time'] = {i: 0 for i in range(1, 9)}
    all_data['served'] = {i: 0 for i in range(1, 9)}

    for param in params:
        random_seed = random.randint(40, 300)
        print(f'PatientService Stream {param["stream_id"]} with RANDOM_SEED = {random_seed}')
        random.seed(random_seed)
        env = simpy.Environment()
        env.process(setup(env, param["arrival_rate"], param["service_rate"], param["num_beds"], param["proportion"], param["stream_id"], all_data))
        env.run(until=sim_time)

    return all_data

def save_data_to_json(all_data, filename='all_data.json'):
    serializable_data = {}
    for key, value in all_data.items():
        if key == 'warm_up_period':
            serializable_data[key] = value
        else:
            serializable_data[key] = {k: v for k, v in value.items()}
    with open(filename, 'w') as f:
        json.dump(serializable_data, f)

def load_data_from_json(filename='all_data.json'):
    with open(filename, 'r') as f:
        data = json.load(f)
    deserialized_data = {}
    for key, value in data.items():
        if key == 'warm_up_period':
            deserialized_data[key] = value
        else:
            deserialized_data[key] = {int(k): v for k, v in value.items()}
    return deserialized_data

def plot_metric_over_time(metric_data, title, xlabel, ylabel, colors, stream_ids, output_file, average_line=None):
    plt.figure(figsize=(10, 6))
    for stream_id, data in metric_data.items():
        if stream_id in stream_ids:
            if isinstance(data, list) and data:
                try:
                    times, values = zip(*data)
                    plt.subplot(2, 2, (stream_id - 1) % 4 + 1)
                    plt.plot(times, values, color=colors[(stream_id - 1)], label=f'Stream {stream_id}')
                    if average_line is not None:
                        plt.axhline(y=average_line[stream_id-1], color='r', linestyle='--', label=f'Average {ylabel} = {average_line[stream_id-1]:.2f}')
                    plt.xlabel(xlabel)
                    plt.ylabel(ylabel)
                    plt.title(f'{title} for Stream {stream_id}')
                    plt.legend()
                except ValueError as e:
                    print(f"Error processing stream {stream_id}: {e}")
            else:
                print(f"No data for Stream {stream_id} or data is not in list format.")
    plt.tight_layout()
    plt.savefig(output_file)
    plt.show()

def plot_distribution(metric_data, title, xlabel, ylabel, colors, stream_ids, output_file):
    plt.figure(figsize=(10, 6))
    for stream_id, data in metric_data.items():
        if stream_id in stream_ids:
            if isinstance(data, list) and data:
                try:
                    mean_value = np.mean(data)
                    max_value = max(data)
                    print(f'Mean {ylabel} for Stream {stream_id}: {mean_value}')
                    print(f'Max {ylabel} for Stream {stream_id}: {max_value}')
                    plt.subplot(2, 2, (stream_id - 1) % 4 + 1)
                    sns.histplot(data, kde=True, color=colors[(stream_id - 1)])
                    plt.xlabel(xlabel)
                    plt.ylabel('Frequency')
                    plt.title(f'{title} for Stream {stream_id}')
                except ValueError as e:
                    print(f"Error processing stream {stream_id}: {e}")
            else:
                print(f"No data for Stream {stream_id} or data is not in list format.")
    plt.tight_layout()
    plt.savefig(output_file)
    plt.show()

def calculate_average_metrics(all_data, params):
    average_L = []
    average_Lq = []
    for param in params:
        arrival_rate = param["arrival_rate"] * (1 - param["proportion"])
        service_rate = param["service_rate"]
        num_beds = param["num_beds"]
        rho = arrival_rate / (num_beds * service_rate)

        # Calculate Pw
        lambda_mu_ratio = arrival_rate / service_rate
        summation_terms = sum((lambda_mu_ratio ** n) / math.factorial(n) for n in range(num_beds))
        numerator_pw = (lambda_mu_ratio ** num_beds) / (math.factorial(num_beds) * (1 - rho))
        Pw = numerator_pw / (summation_terms + numerator_pw)

        # Calculate L and Lq
        L = (arrival_rate / service_rate) + (Pw * rho / (1 - rho))
        Lq = L - (arrival_rate / service_rate)

        print(f"Stream {param['stream_id']}: L = {L}, Lq = {Lq}")

        average_L.append(L)
        average_Lq.append(Lq)
    return average_L, average_Lq

def visualize_results(all_data, params, output_dir='nonhome_nonwarmup_streams_plots_1run'):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    average_L, average_Lq = calculate_average_metrics(all_data, params)

    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'orange']
    plot_metric_over_time(all_data['utilization'], 'Utilization Over Time', 'Time', 'Utilization', colors, range(1, 5), os.path.join(output_dir, 'utilization_1_4.png'))
    plot_metric_over_time(all_data['utilization'], 'Utilization Over Time', 'Time', 'Utilization', colors, range(5, 9), os.path.join(output_dir, 'utilization_5_8.png'))
    plot_metric_over_time(all_data['queue_lengths'], 'Queue Length Over Time', 'Time', 'Queue Length', colors, range(1, 5), os.path.join(output_dir, 'queue_length_1_4.png'), average_line=average_Lq)
    plot_metric_over_time(all_data['queue_lengths'], 'Queue Length Over Time', 'Time', 'Queue Length', colors, range(5, 9), os.path.join(output_dir, 'queue_length_5_8.png'), average_line=average_Lq)
    plot_distribution(all_data['nonzero_waiting_times'], 'Nonzero Waiting Time Distribution', 'Nonzero Waiting Time', 'Nonzero Waiting Time', colors, range(1, 5), os.path.join(output_dir, 'nonzero_waiting_times_1_4.png'))
    plot_distribution(all_data['nonzero_waiting_times'], 'Nonzero Waiting Time Distribution', 'Nonzero Waiting Time', 'Nonzero Waiting Time', colors, range(5, 9), os.path.join(output_dir, 'nonzero_waiting_times_5_8.png'))
    plot_metric_over_time(all_data['num_patients'], 'Number of Patients Over Time', 'Time', 'Number of Patients', colors, range(1, 5), os.path.join(output_dir, 'num_patients_1_4.png'), average_line=average_L)
    plot_metric_over_time(all_data['num_patients'], 'Number of Patients Over Time', 'Time', 'Number of Patients', colors, range(5, 9), os.path.join(output_dir, 'num_patients_5_8.png'), average_line=average_L)
    plot_distribution(all_data['waiting_times'], 'Waiting Time Distribution', 'Waiting Time', 'Waiting Time', colors, range(1, 5), os.path.join(output_dir, 'waiting_times_1_4.png'))
    plot_distribution(all_data['waiting_times'], 'Waiting Time Distribution', 'Waiting Time', 'Waiting Time', colors, range(5, 9), os.path.join(output_dir, 'waiting_times_5_8.png'))
    plot_distribution(all_data['service_times'], 'Service Time Distribution', 'Service Time', 'Service Time', colors, range(1, 5), os.path.join(output_dir, 'service_times_1_4.png'))
    plot_distribution(all_data['service_times'], 'Service Time Distribution', 'Service Time', 'Service Time', colors, range(5, 9), os.path.join(output_dir, 'service_times_5_8.png'))
    plot_distribution(all_data['system_times'], 'System Time Distribution', 'System Time', 'System Time', colors, range(1, 5), os.path.join(output_dir, 'system_times_1_4.png'))
    plot_distribution(all_data['system_times'], 'System Time Distribution', 'System Time', 'System Time', colors, range(5, 9), os.path.join(output_dir, 'system_times_5_8.png'))
    plot_metric_over_time(all_data['throughput'], 'Throughput Over Time', 'Time', 'Throughput', colors, range(1, 5), os.path.join(output_dir, 'throughput_1_4.png'))
    plot_metric_over_time(all_data['throughput'], 'Throughput Over Time', 'Time', 'Throughput', colors, range(5, 9), os.path.join(output_dir, 'throughput_5_8.png'))


def main():

    # 630-24.5/24
    params = [
        {"arrival_rate": 24.5 / 24, "service_rate": 1 / (2.37 * 24), "num_beds": 65, "proportion": 0.0, "stream_id": 1},
        {"arrival_rate": 37 / 24, "service_rate": 1 / (3.02 * 24), "num_beds": 119, "proportion": 0.0, "stream_id": 2},
        {"arrival_rate": 26 / 24, "service_rate": 1 / (4.09 * 24), "num_beds": 115, "proportion": 0.0, "stream_id": 3},
        {"arrival_rate": 19 / 24, "service_rate": 1 / (2.89 * 24), "num_beds": 62, "proportion": 0.0, "stream_id": 4},
        {"arrival_rate": 16.5 / 24, "service_rate": 1 / (3.27 * 24), "num_beds": 62, "proportion": 0.0, "stream_id": 5},
        {"arrival_rate": 14.1 / 24, "service_rate": 1 / (3.51 * 24), "num_beds": 57, "proportion": 0.0, "stream_id": 6},
        {"arrival_rate": 9.8 / 24, "service_rate": 1 / (5.56 * 24), "num_beds": 65, "proportion": 0.0, "stream_id": 7},
        {"arrival_rate": 16.3 / 24, "service_rate": 1 / (4.63 * 24), "num_beds": 85, "proportion": 0.0, "stream_id": 8}
    ]
    warm_up_period = 0
    sim_time = 30000

    if not os.path.exists('all_data.json'):
        all_data = run_simulation(params, warm_up_period, sim_time)
        save_data_to_json(all_data)
    else:
        all_data = load_data_from_json()

    visualize_results(all_data, params)

if __name__ == "__main__":
    main()
