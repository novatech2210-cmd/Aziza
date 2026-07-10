# Performance Baseline

## Memory Usage
```
total        used        free      shared  buff/cache   available
Mem:            49Gi        16Gi       1.1Gi        11Gi        44Gi        33Gi
Swap:          8.0Gi          0B       8.0Gi
```

## CPU Usage
```
top - 18:27:21 up  6:41,  3 users,  load average: 0.16, 0.05, 0.01
Tasks: 251 total,   1 running, 250 sleeping,   0 stopped,   0 zombie
%Cpu(s):  1.1 us,  0.0 sy,  0.0 ni, 98.9 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st 
MiB Mem :  50977.5 total,   1086.1 free,  16525.4 used,  45373.6 buff/cache     
MiB Swap:   8192.0 total,   8192.0 free,      0.0 used.  34452.0 avail Mem 

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
      1 root      20   0   22400  13660   9648 S   0.0   0.0   0:02.37 systemd
      2 root      20   0       0      0      0 S   0.0   0.0   0:00.01 kthreadd
      3 root      20   0       0      0      0 S   0.0   0.0   0:00.00 pool_wo+
```

## GPU Consumption
```
Fri Jul 10 18:27:21 2026       
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.309.01             Driver Version: 535.309.01   CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA RTX A6000               Off | 00000000:06:10.0 Off |                  Off |
| 30%   47C    P8              22W / 300W |  28826MiB / 49140MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
                                                                                         
+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|    0   N/A  N/A      5838      C   /root/aziza-build/venv312/bin/python3      1070MiB |
|    0   N/A  N/A      5872      C   /root/aziza-build/venv312/bin/python3     10694MiB |
|    0   N/A  N/A      6120      C   /root/aziza-build/venv312/bin/python3     17028MiB |
+---------------------------------------------------------------------------------------+
```
