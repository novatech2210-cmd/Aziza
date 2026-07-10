import os
import paramiko
import sys

def run_cmd(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(os.environ.get("AZIZA_SSH_HOST", ""), username='aziza', password=os.environ.get("AZIZA_SSH_PASS", ""))
        stdin, stdout, stderr = client.exec_command(cmd)
        
        # Read the output
        print("STDOUT:")
        print(stdout.read().decode('utf-8'))
        print("STDERR:")
        print(stderr.read().decode('utf-8'))
        
        # Get exit status
        exit_status = stdout.channel.recv_exit_status()
        print(f"EXIT_STATUS: {exit_status}")
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_cmd(sys.argv[1])
