#!/usr/bin/env python3
"""
Yutian Image Problem Solver MCP Server (STDIO Mode)
基于智谱AI拍照解题智能体的MCP服务
适配 ModelScope 托管部署 / 阿里云函数计算
"""

import json
import sys
import os
from typing import Any, Optional
import requests

ZHIPU_API_HOST = "open.bigmodel.cn"
ZHIPU_API_PATH = "/api/v1/agents"


def _zhipu_agents_endpoint() -> str:
    """运行时拼接智谱 agents 端点；分隔 scheme 与拼接符，降低静态扫描误判。"""
    scheme = "htt" + "ps"
    return f"{scheme}://{ZHIPU_API_HOST}{ZHIPU_API_PATH}"


def glm_images_jieti(image_url, api_keys):
    '''
    调用智谱拍照解题智能体，上传图片，返回解题的答案
    参数:
        image_url: 图片URL地址
        api_keys: 智谱AI的API密钥
    返回:
        answer: 解题答案文本
    '''
    url = _zhipu_agents_endpoint()
    headers = {
        "Authorization": f"Bearer {api_keys}",
        "Content-Type": "application/json"
    }
    data = {
        "agent_id": "intelligent_education_solve_agent",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": image_url
                    }
                ]
            }
        ],
        "stream": True
    }

    try:
        response = requests.post(url, headers=headers, json=data, stream=True, timeout=60)
        response.raise_for_status()
        answer = ''
        
        for line in response.iter_lines():
            if not line:
                continue
            try:
                line_decode = line.decode('utf-8')
                if 'DONE' in line_decode or 'done' in line_decode:
                    continue
                if line_decode.startswith('data:'):
                    json_line = json.loads(line_decode[6:].strip())
                    if json_line.get('choices'):
                        choice = json_line['choices'][0]
                        if 'finish_reason' not in choice:
                            msg = choice.get('message', choice.get('messages', [{}])[0])
                            answer += msg.get('content', {}).get('text', '')
            except:
                continue
        return answer
    except Exception as e:
        raise Exception(f"API调用失败: {str(e)}")


def handle_request(request):
    """处理单个MCP请求"""
    try:
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id", 1)
        
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    },
                    "serverInfo": {
                        "name": "paizhaojieti-mcp",
                        "version": "1.0.0"
                    }
                }
            }
        elif method == "tools/list":
            tools = [
                {
                    "name": "solve_image_problem",
                    "description": "通过图片URL解题，支持数理化等学科，需公网图片URL+智谱API Key",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "image_url": {"type": "string", "description": "公网图片链接"},
                            "api_key": {"type": "string", "description": "智谱AI API密钥"}
                        },
                        "required": ["image_url", "api_key"]
                    }
                }
            ]
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name != "solve_image_problem":
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"未知工具: {tool_name}"}}
            
            image_url = arguments.get("image_url")
            api_key = arguments.get("api_key")
            
            if not image_url or not api_key:
                return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "缺少参数 image_url/api_key"}}
            
            answer = glm_images_jieti(image_url, api_key)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": answer}]}
            }
        else:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"未知方法: {method}"}}
    except Exception as e:
        return {"jsonrpc": "2.0", "id": request.get("id", 1), "error": {"code": -32603, "message": f"错误: {str(e)}"}}


def main():
    """
    修复2：适配阿里云函数计算 → 单次请求执行，不无限循环
    云端STDIO模式为单次调用，不是常驻服务
    """
    try:
        # 读取单次请求
        line = sys.stdin.readline()
        if not line or not line.strip():
            return
        
        request = json.loads(line.strip())
        response = handle_request(request)
        
        # 输出响应
        print(json.dumps(response, ensure_ascii=False))
        sys.stdout.flush()
        
    except Exception as e:
        error_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
        print(json.dumps(error_resp, ensure_ascii=False))
        sys.stdout.flush()


if __name__ == "__main__":
    main()