import os
import paramiko
import sys

def push_file(local_path, remote_path):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(os.environ.get("AZIZA_SSH_HOST", ""), username='aziza', password=os.environ.get("AZIZA_SSH_PASS", ""))
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        print("File pushed successfully")
    finally:
        client.close()

if __name__ == "__main__":
    push_file(sys.argv[1], sys.argv[2])
