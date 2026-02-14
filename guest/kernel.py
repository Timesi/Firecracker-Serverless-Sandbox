import sys
import json
import io
import traceback
from contextlib import redirect_stdout, redirect_stderr

# 全局记忆
GLOBAL_CONTEXT = {}

def main(): 
    while True:
        try:
            # 1. 阻塞等待 Supervisor 派发任务 (按行读取)
            line = sys.stdin.readline()
            if not line:
                break       # 如果 Supervisor 断开了管道，就退出

            req = json.loads(line)
            code = req.get("code", "")

            # 2. 拦截输出并执行代码
            f = io.StringIO()
            status = "success"

            try:
                with redirect_stdout(f), redirect_stderr(f):
                    exec(code, GLOBAL_CONTEXT)
                output = f.getvalue()
            except Exception:
                status = "error"
                output = f.getvalue() + "\n" + traceback.format_exc()
            except SystemExit as e:
                status = "error"
                output = f.getvalue() + f"\n[拦截] 恶意操作: 试图退出系统 (代码 {e})"
            
            # 3. 将结果打包为 JSON 字符串，打印回给 Supervisor
            res = {"status": status, "output": output}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush() # 必须 flush，否则对方收不到
        except Exception as e:
            sys.stdout.write(json.dumps({"status": "fatal", "output": str(e)}) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
