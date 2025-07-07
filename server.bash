# 该bash是为了后台启动gunicorn
nohup gunicorn -w 8 -b 127.0.0.1:5053 main:app &> ./logs/gunicorn.log &