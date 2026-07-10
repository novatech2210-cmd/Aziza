cd /root/aziza-build
git config --global --add safe.directory /root/aziza-build
git init
printf "node_modules/\nvenv/\ncloudflared\n*.log\n__pycache__/\n.env\nmodels/\nhuggingface/\n*.safetensors\n*.pt\n*.bin\ncheckpoint-*/\n" > .gitignore
git config user.email 'admin@novatech.com'
git config user.name 'novatech2210'
git add .
git commit -m 'Initial commit of AZIZA build from GPU server'
git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin https://${GITHUB_TOKEN}@github.com/novatech2210-cmd/AZIZA-Remote-Build.git
git push -u origin main
git remote remove origin
git remote add origin https://github.com/novatech2210-cmd/AZIZA-Remote-Build.git
