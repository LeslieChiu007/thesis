import numpy as np
import math

def erlangB_lostpro(s, a):
    n = 0
    B = 1
    while n < s:
        n += 1
        B = a * B / (n + a * B)
    return B

def erlangC(s, a):
    X = erlangB_lostpro(s, a)
    return s * X / (s - a * (1 - X)) if a / s < 1 else 1

def den(s, a):
    num = a**s
    den = math.factorial(s)*(1 - a/s)
    return num/den

def calculate_metrics(param):
    lamb = param["arrival_rate"] * (1 - param["proportion"])
    a = lamb / param["service_rate"]
    s = param["num_beds"]
    ErlangC_value = erlangC(s, a)
    rho = a / s
    P0 = ErlangC_value / den(s, a)   # first get erlangC value, then derive P0

    # Theoretical values
    W_time = ErlangC_value / ((1 - rho) * s * param["service_rate"])
    W_time_nonzero = 1 / ((1 - rho) * s * param["service_rate"])
    scale_param = W_time_nonzero
    W_size = lamb * W_time
    S_size = W_size + a
    Service_time = 1 / param["service_rate"]
    Sojourn_time = W_time + Service_time
    Throughput = lamb
    return {
        "a": a,
        "ErlangC_value": ErlangC_value,
        "P0": P0,

        "W_size": W_size,
        "S_size": S_size,
        "W_time": W_time,
        "W_time_nonzero": W_time_nonzero,
        "scale_param": scale_param,
        "Service_time": Service_time,
        "Sojourn_time": Sojourn_time,
        "rho": rho,
        "lamb": lamb,
        "Throughput": Throughput
    }

def main():
    # 630-24.5/24
    params_streams = [
        {"arrival_rate": 24.5 / 24, "service_rate": 1 / (2.37 * 24), "num_beds": 65, "proportion": 0.0, "stream_id": 1},
        {"arrival_rate": 37 / 24, "service_rate": 1 / (3.02 * 24), "num_beds": 119, "proportion": 0.0, "stream_id": 2},
        {"arrival_rate": 26 / 24, "service_rate": 1 / (4.09 * 24), "num_beds": 115, "proportion": 0.0, "stream_id": 3},
        {"arrival_rate": 19 / 24, "service_rate": 1 / (2.89 * 24), "num_beds": 62, "proportion": 0.0, "stream_id": 4},
        {"arrival_rate": 16.5 / 24, "service_rate": 1 / (3.27 * 24), "num_beds": 62, "proportion": 0.0, "stream_id": 5},
        {"arrival_rate": 14.1 / 24, "service_rate": 1 / (3.51 * 24), "num_beds": 57, "proportion": 0.0, "stream_id": 6},
        {"arrival_rate": 9.8 / 24, "service_rate": 1 / (5.56 * 24), "num_beds": 65, "proportion": 0.0, "stream_id": 7},
        {"arrival_rate": 16.3 / 24, "service_rate": 1 / (4.63 * 24), "num_beds": 85, "proportion": 0.0, "stream_id": 8},
        {"arrival_rate": 4, "service_rate": 1 / 2.4, "num_beds": 10, "proportion": 0, "stream_id": 9},
        {"arrival_rate": 5, "service_rate": 6, "num_beds": 3, "proportion": 0, "stream_id": 10},
    ]

    for param in params_streams:
        metrics = calculate_metrics(param)
        print(f'PatientService Stream {param["stream_id"]} with Offered Load = {metrics["a"]}')
        print(f'PatientService Stream {param["stream_id"]} with Carried Load = {metrics["a"]}')
        print(f'PatientService Stream {param["stream_id"]} with ErlangC Value = {metrics["ErlangC_value"]}')
        print(f'PatientService Stream {param["stream_id"]} with the Probablity of Zero Customer = {metrics["P0"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Queue Size = {metrics["W_size"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Number of Patients in the System = {metrics["S_size"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Wait Time = {metrics["W_time"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Nonzero Wait Time = {metrics["W_time_nonzero"]}')
        print(f'PatientService Stream {param["stream_id"]} with scale_param for nonzero wait time  = {metrics["scale_param"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Service Time = {metrics["Service_time"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Sojourn Time = {metrics["Sojourn_time"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Utilization = {metrics["rho"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Arrival Rate = {metrics["lamb"]}')
        print(f'PatientService Stream {param["stream_id"]} with Mean Throughput = {metrics["Throughput"]}')
        print('-----------------------------------')


if __name__ == "__main__":
    main()
