from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os, sys

from app.pool import SandboxPool
from app.client import send_code_to_vm

# 安全检查：API 也必须拥有操作 Jailer 的 Root 权限
# Jailer 需要设置 cgroups, chroot, netns 等底层隔离特性，非 Root 无法操作。
if os.geteuid() != 0:
    print("❌ 致命错误：必须使用 sudo 启动 API 服务！")
    sys.exit(1)

app = FastAPI(title="Firecracker Sandbox API")
# 全局沙盒池：管理当前所有运行中的虚拟机实例
pool = SandboxPool()

class ExecuteRequest(BaseModel):
    code: str

@app.post("/sandbox")
def create_sandbox():
    """创建一个新的独立虚拟机"""
    try:
        vm_id = pool.create_sandbox()
        return {"vm_id": vm_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sandbox/{vm_id}/execute")
def execute_code(vm_id: str, req: ExecuteRequest):
    """在指定的虚拟机内执行代码"""
    sandbox = pool.get_sandbox(vm_id)
    if not sandbox:
        raise HTTPException(status_code=404, detail="找不到该沙盒，可能已被销毁")
    
    result = send_code_to_vm(vm_id, req.code)
    return result

@app.delete("/sandbox/{vm_id}")
def delete_sandbox(vm_id: str):
    """销毁指定的虚拟机"""
    pool.destroy_sandbox(vm_id)
    return {"status": "deleted"}

# 优雅关闭：当 API 停止时，干掉所有还在跑的虚拟机
@app.on_event("shutdown")
def shutdown_event():
    print("🛑 正在清理所有活动的沙盒...")
    pool.destroy_all()
