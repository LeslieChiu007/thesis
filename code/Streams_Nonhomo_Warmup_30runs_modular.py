import simpy
import numpy as np
import random
import itertools
import math
import scipy.stats
import matplotlib.pyplot as plt
import seaborn as sns
import multiprocessing as mp
import json
import time
import logging
import os

class PatientService:
    def __init__(self, env, num_beds, servicetime):
        self.env = env
        self.bed = simpy.Resource(env, num_beds)
        self.servicetime = servicetime

    def serve(self, patient):
        yield self.env.timeout(np.random.exponential(scale=self.servicetime))
        # yield self.env.timeout(random.expovariate(1/self.servicetime))
        # yield self.env.timeout((-self.servicetime) * math.log(1 - random.uniform(0,1)))

def patient(env, name, ps, num_beds, proportion, stream_id, results):
    arrive = env.now

    # Only track arrivals after the warm-up period
    if arrive > results["WARM_UP_PERIOD"]:
        results["total_arrivals"][stream_id] += 1  # Increment the count of arrivals

    if random.random() < proportion:
        results["leaving_patients"][stream_id].append((arrive, stream_id))
        return

    if arrive > results["WARM_UP_PERIOD"]:
        results["queue_lengths"][stream_id].append((env.now, len(ps.bed.queue)))
        results["num_patients"][stream_id].append((env.now, len(ps.bed.queue) + len(ps.bed.users)))

    with ps.bed.request() as request:
        yield request
        wait = env.now - arrive

        if arrive > results["WARM_UP_PERIOD"]:
            results["wait_times"][stream_id].append(wait)
            if wait > 0:
                results["nonzero_wait_times"][stream_id].append(wait)

        service_start = env.now
        yield env.process(ps.serve(name))
        service_time = env.now - service_start
        if arrive > results["WARM_UP_PERIOD"]:
            results["service_times"][stream_id].append(service_time)
            results["sojourn_times"][stream_id].append(wait + service_time)
            results["total_service_time"][stream_id] += service_time
            utilization = results["total_service_time"][stream_id] / (num_beds * (env.now - results["WARM_UP_PERIOD"]))
            results["utilization_over_time"][stream_id].append((env.now, utilization))
            results["served"][stream_id] += 1
            results["throughput"][stream_id].append((env.now, results["served"][stream_id] / (env.now - results["WARM_UP_PERIOD"])))

# for dynamic arrival rates with sinusoidal function
def setup(env, base_arrival_rate, service_rate, num_beds, proportion, stream_id, results):
    patientservice = PatientService(env, num_beds, 1 / service_rate)
    patient_count = itertools.count()

    max_arrival_rate = base_arrival_rate * 2  # Maximum rate considering the sinusoidal fluctuation

    while True:
        interarrival_time = np.random.exponential(scale=1 / max_arrival_rate)
        # interarrival_time = random.expovariate(max_arrival_rate)
        # interarrival_time = (-1/max_arrival_rate) * math.log(1 - random.uniform(0,1))

        yield env.timeout(interarrival_time)

        t = env.now
        current_arrival_rate = base_arrival_rate + 1 * base_arrival_rate * math.sin(math.pi * t / 12)

        if random.random() <= current_arrival_rate / max_arrival_rate:
            env.process(patient(env, f'Patient {next(patient_count)}', patientservice, num_beds, proportion, stream_id, results))

# for PP (static arrival rate)
# def setup(env, base_arrival_rate, service_rate, num_beds, proportion, stream_id, results):
#     patientservice = PatientService(env, num_beds, 1 / service_rate)
#     patient_count = itertools.count()
#     while True:
#         t = env.now
#         current_arrival_rate = base_arrival_rate
#         # interarrival_time = np.random.exponential(scale=1 / current_arrival_rate)
#         interarrival_time = np.random.exponential(scale=1 / current_arrival_rate)
#         # interarrival_time = (-1/current_arrival_rate) * math.log(1 - random.uniform(0,1))
#
#         yield env.timeout(interarrival_time)
#         env.process(patient(env, f'Patient {next(patient_count)}', patientservice, num_beds, proportion, stream_id, results))

# # all arrivals occur between 9am and 12pm with uniform distribution every day
# def setup(env, base_arrival_rate, service_rate, num_beds, proportion, stream_id, results):
#     patientservice = PatientService(env, num_beds, 1 / service_rate)
#     patient_count = itertools.count()
#
#     # Total number of arrivals in a 24-hour period
#     total_arrivals_per_day = base_arrival_rate * 24  # Total number of arrivals in a 24-hour period
#     peak_hours_duration = 3  # The 3-hour period (9 AM to 12 PM)
#     # arrivals_per_peak_period = total_arrivals_per_day  # All arrivals happen in this 3-hour period
#     # Interarrival time: how often arrivals should occur within the peak period
#     interarrival_time = peak_hours_duration / total_arrivals_per_day
#
#     while True:
#         t = env.now
#
#         # Determine the current day based on the time elapsed
#         current_day = int(t // 24)
#
#         # Calculate the peak hours for the current day (9 AM to 12 PM, shifted each day)
#         peak_start_time = 9 + current_day * 24  # Start of the 3-hour window
#         peak_end_time = 12 + current_day * 24  # End of the 3-hour window
#
#         # Only allow arrivals between 9 AM and 12 PM of each day
#         if peak_start_time <= t < peak_end_time:
#             # Arrivals occur uniformly within the 3-hour window
#             for _ in range(int(total_arrivals_per_day)):
#                 yield env.timeout(interarrival_time)  # Uniformly spaced inter-arrival times
#                 env.process(patient(env, f'Patient {next(patient_count)}', patientservice, num_beds, proportion, stream_id, results))
#
#             # After processing all arrivals for the day, fast-forward to the next day's 9 AM
#             time_until_next_peak = 24 - (t - peak_start_time)  # Skip to 9 AM of the next day
#             yield env.timeout(time_until_next_peak)
#             # print(f'Skipping to next day, time now {env.now}')
#         else:
#             # Fast-forward the simulation to the next day's peak start time
#             next_peak_start_time = 9 + (current_day + 1) * 24
#             time_until_next_peak = next_peak_start_time - t
#             yield env.timeout(time_until_next_peak)
# # #             # print(f'Skipping to next day, time now {env.now}')

def run_simulation(run, params, whole_run_leaving_patients, WARM_UP_PERIOD=10000, SIM_TIME=30000):
    # RANDOM_SEED = random.randint(40, 50)
    # random.seed(RANDOM_SEED)
    # np.random.seed(RANDOM_SEED)
    results = {
        "WARM_UP_PERIOD": WARM_UP_PERIOD,
        "total_arrivals": {i: 0 for i in range(1, 9)},  # Track total arrivals after warm-up

        "leaving_patients": {i: [] for i in range(1, 9)},
        "queue_lengths": {i: [] for i in range(1, 9)},
        "num_patients": {i: [] for i in range(1, 9)},
        "wait_times": {i: [] for i in range(1, 9)},
        "nonzero_wait_times": {i: [] for i in range(1, 9)},
        "service_times": {i: [] for i in range(1, 9)},
        "sojourn_times": {i: [] for i in range(1, 9)},
        "total_service_time": {i: 0 for i in range(1, 9)},

        "utilization_over_time": {i: [] for i in range(1, 9)},
        "served": {i: 0 for i in range(1, 9)},
        "throughput": {i: [] for i in range(1, 9)},

    }
    for param in params:
        env = simpy.Environment()
        env.process(setup(env, param["arrival_rate"], param["service_rate"], param["num_beds"], param["proportion"], param["stream_id"], results))
        env.run(until=SIM_TIME)

    # for the tuples, get the numbers
    mean_queue_lengths = {i: np.mean([q[1] for q in results["queue_lengths"][i]]) for i in range(1, 9) if results["queue_lengths"][i]}
    mean_num_patients = {i: np.mean([n[1] for n in results["num_patients"][i]]) for i in range(1, 9) if results["num_patients"][i]}
    mean_service_times = {i: np.mean(results["service_times"][i]) for i in range(1, 9) if results["service_times"][i]}
    mean_sojourn_times = {i: np.mean(results["sojourn_times"][i]) for i in range(1, 9) if results["sojourn_times"][i]}
    mean_throughput = {i: np.mean([t[1] for t in results["throughput"][i]]) for i in range(1, 9) if results["throughput"][i]}
    mean_wait_times = {i: np.mean(results["wait_times"][i]) for i in range(1, 9) if results["wait_times"][i]}
    mean_nonzero_wait_times = {i: np.mean(results["nonzero_wait_times"][i]) for i in range(1, 9) if results["nonzero_wait_times"][i]}
    last_utilization = {i: results["utilization_over_time"][i][-1][1] for i in range(1, 9) if results["utilization_over_time"][i]}

    # Calculate the arrival rates after warm-up
    mean_arrival_rates = {i: results["total_arrivals"][i] / (SIM_TIME - WARM_UP_PERIOD) for i in range(1, 9)}

    whole_run_leaving_patients[run] = results["leaving_patients"]

    # each run has the following metrics
    return results["leaving_patients"], mean_queue_lengths, mean_num_patients, mean_wait_times, mean_nonzero_wait_times, mean_service_times, mean_sojourn_times, last_utilization, mean_throughput, mean_arrival_rates

def calculate_confidence_interval(data):
    confidence_level = 0.95
    degrees_freedom = len(data) - 1
    sample_mean = np.mean(data)
    sample_standard_error = scipy.stats.sem(data)
    confidence_interval = scipy.stats.t.interval(confidence_level, degrees_freedom, loc=sample_mean, scale=sample_standard_error)
    return confidence_interval

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
        {"arrival_rate": 16.3 / 24, "service_rate": 1 / (4.63 * 24), "num_beds": 85, "proportion": 0.0, "stream_id": 8},
        # {"arrival_rate": 4, "service_rate": 1/2.4, "num_beds": 10, "proportion": 0.0, "stream_id": 7},
        # {"arrival_rate": 5, "service_rate": 6, "num_beds": 3, "proportion": 0.0, "stream_id": 8}

    ]
    num_runs = 50    # 50
    warm_up_period = 10000
    sim_time = 30000

    whole_run_leaving_patients = {run: {i: [] for i in range(1, 9)} for run in range(1, num_runs + 1)}

    aggregated_mean_queue_lengths = {i: [] for i in range(1, 9)}
    aggregated_mean_num_patients = {i: [] for i in range(1, 9)}
    aggregated_mean_service_times = {i: [] for i in range(1, 9)}
    aggregated_mean_sojourn_times = {i: [] for i in range(1, 9)}
    aggregated_mean_throughput = {i: [] for i in range(1, 9)}
    aggregated_mean_wait_times = {i: [] for i in range(1, 9)}
    aggregated_mean_nonzero_wait_times = {i: [] for i in range(1, 9)}
    aggregated_last_utilization = {i: [] for i in range(1, 9)}
    aggregated_mean_arrival_rates = {i: [] for i in range(1, 9)}

    start_time = time.time()
    pool = mp.Pool(mp.cpu_count())
    results = pool.starmap(run_simulation, [(run, params, whole_run_leaving_patients, warm_up_period, sim_time) for run in range(1, num_runs + 1)])
    pool.close()
    pool.join()

    for run, (lps, mql, mnp, mwt, mnwt, mst, msojt, lu, mt, mar) in enumerate(results, 1):
        for i in range(1, 9):
            if i in mql and mql[i]:
                aggregated_mean_queue_lengths[i].append(mql[i])
            if i in mnp and mnp[i]:
                aggregated_mean_num_patients[i].append(mnp[i])
            if i in mwt and mwt[i]:
                aggregated_mean_wait_times[i].append(mwt[i])
            if i in mnwt and mnwt[i]:
                aggregated_mean_nonzero_wait_times[i].append(mnwt[i])
            if i in mst and mst[i]:
                aggregated_mean_service_times[i].append(mst[i])
            if i in msojt and msojt[i]:
                aggregated_mean_sojourn_times[i].append(msojt[i])
            if i in lu and lu[i]:
                aggregated_last_utilization[i].append(lu[i])
            if i in mt and mt[i]:
                aggregated_mean_throughput[i].append(mt[i])
            if i in mar and mar[i]:
                aggregated_mean_arrival_rates[i].append(mar[i])

    end_time = time.time()
    print(f"Total execution time: {end_time - start_time} seconds")

    # Calculate confidence intervals for all metrics
    confidence_intervals_queue_length = {i: calculate_confidence_interval(aggregated_mean_queue_lengths[i]) for i in range(1, 9)}
    confidence_intervals_num_patient = {i: calculate_confidence_interval(aggregated_mean_num_patients[i]) for i in range(1, 9)}
    confidence_intervals_service_time = {i: calculate_confidence_interval(aggregated_mean_service_times[i]) for i in range(1, 9)}
    confidence_intervals_sojourn_time = {i: calculate_confidence_interval(aggregated_mean_sojourn_times[i]) for i in range(1, 9)}
    confidence_intervals_throughput = {i: calculate_confidence_interval(aggregated_mean_throughput[i]) for i in range(1, 9)}
    confidence_intervals_wait_time = {i: calculate_confidence_interval(aggregated_mean_wait_times[i]) for i in range(1, 9)}
    confidence_intervals_nonzero_wait_time = {i: calculate_confidence_interval(aggregated_mean_nonzero_wait_times[i]) for i in range(1, 9)}
    confidence_intervals_utilization = {i: calculate_confidence_interval(aggregated_last_utilization[i]) for i in range(1, 9)}
    confidence_intervals_arrival_rate = {i: calculate_confidence_interval(aggregated_mean_arrival_rates[i]) for i in range(1, 9)}

    # Print mean values and confidence intervals for all metrics
    mean_values_queue_length = {i: np.mean(aggregated_mean_queue_lengths[i]) for i in range(1, 9)}
    mean_values_num_patient = {i: np.mean(aggregated_mean_num_patients[i]) for i in range(1, 9)}
    mean_values_service_time = {i: np.mean(aggregated_mean_service_times[i]) for i in range(1, 9)}
    mean_values_sojourn_time = {i: np.mean(aggregated_mean_sojourn_times[i]) for i in range(1, 9)}
    mean_values_throughput = {i: np.mean(aggregated_mean_throughput[i]) for i in range(1, 9)}
    mean_values_wait_time = {i: np.mean(aggregated_mean_wait_times[i]) for i in range(1, 9)}
    mean_values_nonzero_wait_time = {i: np.mean(aggregated_mean_nonzero_wait_times[i]) for i in range(1, 9)}
    mean_values_utilization = {i: np.mean(aggregated_last_utilization[i]) for i in range(1, 9)}
    mean_values_arrival_rate = {i: np.mean(aggregated_mean_arrival_rates[i]) for i in range(1, 9)}

    for i in range(1, 9):
        print(f'Mean value of the queue length for Stream {i} is', mean_values_queue_length[i])
        print(f'Mean value of the number of patients for Stream {i} is', mean_values_num_patient[i])
        print(f'Mean value of the wait time for Stream {i} is', mean_values_wait_time[i])
        print(f'Mean value of the nonzero wait time for Stream {i} is', mean_values_nonzero_wait_time[i])
        print(f'Mean value of the service time for Stream {i} is', mean_values_service_time[i])
        print(f'Mean value of the sojourn time for Stream {i} is', mean_values_sojourn_time[i])
        print(f'Mean value of the utilization for Stream {i} is', mean_values_utilization[i])
        print(f'Mean value of the arrival rate for Stream {i} is', mean_values_arrival_rate[i])
        print(f'Mean value of the throughput for Stream {i} is', mean_values_throughput[i])
        print("        ")
        print(f'95% confidence interval of the queue length for Stream {i} is', confidence_intervals_queue_length[i])
        print(f'95% confidence interval of the number of patients for Stream {i} is', confidence_intervals_num_patient[i])
        print(f'95% confidence interval of the wait time for Stream {i} is', confidence_intervals_wait_time[i])
        print(f'95% confidence interval of the nonzero wait time for Stream {i} is', confidence_intervals_nonzero_wait_time[i])
        print(f'95% confidence interval of the service time for Stream {i} is', confidence_intervals_service_time[i])
        print(f'95% confidence interval of the sojourn time for Stream {i} is', confidence_intervals_sojourn_time[i])
        print(f'95% confidence interval of the utilization for Stream {i} is', confidence_intervals_utilization[i])
        print(f'95% confidence interval of the arrival rate for Stream {i} is', confidence_intervals_arrival_rate[i])
        print(f'95% confidence interval of the throughput for Stream {i} is', confidence_intervals_throughput[i])
        print('-----------------------------------')

if __name__ == '__main__':
    main()
