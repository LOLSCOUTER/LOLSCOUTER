import time
import subprocess

while True:
    print("사용자 목록 수집 중")
    subprocess.run(["python", "user_collector.py"], check=True)

    print("매치 수집 및 학습 중")
    subprocess.run(["python", "app.py"], check=True)

    print("1분 대기 후 다음 주기 시작")
    time.sleep(60)  
