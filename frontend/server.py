#!/usr/bin/env python
# coding: utf-8

import os
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn

# 初始化FastAPI应用
app = FastAPI(title="Hierarchical Agent Teams", description="Hierarchical Agent Teams Demo With Vue.js")

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 挂载静态文件目录 - 将css目录明确挂载到/css路径
app.mount("/css", StaticFiles(directory=os.path.join(current_dir, "css")), name="css")
# 挂载js目录到/js路径
app.mount("/js", StaticFiles(directory=os.path.join(current_dir, "js")), name="js")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(current_dir, "vue-app.html"))

# 如果直接运行此文件，启动前端服务器
if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=9000, reload=True)
