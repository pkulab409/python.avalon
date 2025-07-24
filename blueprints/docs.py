#!/usr/bin/env python
# dmcnczy 25/4/28
"""提供文档页面"""


from flask import Blueprint, render_template, abort
import os

# 创建蓝图
docs_bp = Blueprint("docs", __name__)


@docs_bp.route("/")
def index():
    return render_template("/docs/docs.html")


# 统一所有 /docs/<name> 路由，前端负责加载 md
@docs_bp.route("/<name>")
def docs_page(name):
    # 只渲染 docs.html，由前端决定加载哪个 md
    return render_template("/docs/docs.html")
