import subprocess
import time

def run_script(path):
    result = subprocess.run(["python", path], capture_output=True, text=True)
    print(result.stdout)

if __name__ == "__main__":
    print("시작\n")
    while True:
        print("비동기 유저 기반 매치 수집")
        run_script("async_team_collector.py")

        print("모델 학습 및 평가")
        run_script("train_model.py")

        print("다음 루프까지 대기\n")
        time.sleep(5)  