import os
import paramiko
import sys

def run_remote_command(host, user, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(hostname=host, username=user, password=password, timeout=10)
        stdin, stdout, stderr = client.exec_command(command)
        
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8')
        err = stderr.read().decode('utf-8')
        
        if out:
            print(out, end='')
        if err:
            print(err, file=sys.stderr, end='')
            
        sys.exit(exit_status)
    except Exception as e:
        print(f"Error connecting or running command: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python remote_exec.py 'command'", file=sys.stderr)
        sys.exit(1)
        
    cmd = " ".join(sys.argv[1:])
    run_remote_command(os.environ.get("AZIZA_SSH_HOST", ""), 'aziza', os.environ.get("AZIZA_SSH_PASS", ""), cmd)
