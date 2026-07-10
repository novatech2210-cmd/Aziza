import torch
print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('Device count:', torch.cuda.device_count())
    print('Current device:', torch.cuda.current_device())
    props = torch.cuda.get_device_properties(0)
    print('Device name:', props.name)
    print('Total memory (GB):', props.total_memory / 1e9)
    print('Free memory (GB):', torch.cuda.mem_get_info()[0] / 1e9)
    print('Total memory from mem_get_info (GB):', torch.cuda.mem_get_info()[1] / 1e9)

