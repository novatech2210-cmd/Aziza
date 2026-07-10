import os
import pexpect
import sys

def run_cmd():
    ssh_host = os.environ.get("PROXMOX_HOST", "")
    ssh_pass = os.environ.get("PROXMOX_SSH_PASS", "")
    mongo_admin_user = os.environ.get("MONGO_ADMIN_USER", "")
    mongo_admin_pass = os.environ.get("MONGO_ADMIN_PASS", "")
    mongo_app_user = os.environ.get("MONGO_APP_USER", "")
    mongo_app_pass = os.environ.get("MONGO_APP_PASS", "")
    
    child = pexpect.spawn(f"ssh -o StrictHostKeyChecking=no -p 122 pers@{ssh_host}", encoding='utf-8')
    child.expect("password:")
    child.sendline(ssh_pass)
    child.expect(r"[\$#] ")
    
    # 1. Create admin user
    print("Creating admin user...")
    child.sendline(f'mongosh admin --eval "db.createUser({{user: \'{mongo_admin_user}\', pwd: \'{mongo_admin_pass}\', roles: [{{role: \'userAdminAnyDatabase\', db: \'admin\'}}]}})"')
    child.expect(r"[\$#] ")
    print(child.before)
    
    # 2. Create aziza database and user
    print("Creating aziza user...")
    child.sendline(f'mongosh aziza --eval "db.createUser({{user: \'{mongo_app_user}\', pwd: \'{mongo_app_pass}\', roles: [{{role: \'readWrite\', db: \'aziza\'}}]}})"')
    child.expect(r"[\$#] ")
    print(child.before)
    
    # 3. Enable auth in mongod.conf
    print("Enabling auth in mongod.conf...")
    child.sendline('sudo sed -i "s/#security:/security:\\n  authorization: enabled/" /etc/mongod.conf')
    index = child.expect([r"\[sudo\] password for pers:", r"[\$#] "])
    if index == 0:
        child.sendline(ssh_pass)
        child.expect(r"[\$#] ")
        
    # 4. Restart mongod
    print("Restarting mongod...")
    child.sendline('sudo systemctl restart mongod')
    child.expect(r"[\$#] ")
    print(child.before)
    
    child.sendline("exit")

if __name__ == "__main__":
    run_cmd()
