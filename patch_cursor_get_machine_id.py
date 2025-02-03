#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
from typing import Tuple


# 配置日志
def setup_logging() -> logging.Logger:
    """配置并返回logger实例"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


logger = setup_logging()


def get_cursor_paths() -> Tuple[str, str]:
    """
    根据不同操作系统获取 Cursor 相关路径

    Returns:
        Tuple[str, str]: (package.json路径, main.js路径)的元组

    Raises:
        OSError: 当找不到有效路径或系统不支持时抛出
    """
    system = platform.system()

    paths_map = {
        "Darwin": {
            "base": "/Applications/Cursor.app/Contents/Resources/app",
            "package": "package.json",
            "main": "out/main.js",
        },
        "Windows": {
            "base": os.path.join(
                os.getenv("LOCALAPPDATA", ""), "Programs", "Cursor", "resources", "app"
            ),
            "package": "package.json",
            "main": "out/main.js",
        },
        "Linux": {
            "bases": ["/opt/Cursor/resources/app", "/usr/share/cursor/resources/app"],
            "package": "package.json",
            "main": "out/main.js",
        },
    }

    if system not in paths_map:
        raise OSError(f"不支持的操作系统: {system}")

    if system == "Linux":
        for base in paths_map["Linux"]["bases"]:
            pkg_path = os.path.join(base, paths_map["Linux"]["package"])
            if os.path.exists(pkg_path):
                return (pkg_path, os.path.join(base, paths_map["Linux"]["main"]))
        raise OSError("在 Linux 系统上未找到 Cursor 安装路径")

    base_path = paths_map[system]["base"]
    return (
        os.path.join(base_path, paths_map[system]["package"]),
        os.path.join(base_path, paths_map[system]["main"]),
    )


def check_system_requirements(pkg_path: str, main_path: str) -> bool:
    """
    检查系统要求

    Args:
        pkg_path: package.json 文件路径
        main_path: main.js 文件路径

    Returns:
        bool: 检查是否通过
    """
    for file_path in [pkg_path, main_path]:
        if not os.path.isfile(file_path):
            logger.error(f"文件不存在: {file_path}")
            return False

        if not os.access(file_path, os.W_OK):
            logger.error(f"没有文件写入权限: {file_path}")
            return False

    return True


def version_check(version: str, min_version: str = "", max_version: str = "") -> bool:
    """
    版本号检查

    Args:
        version: 当前版本号
        min_version: 最小版本号要求
        max_version: 最大版本号要求

    Returns:
        bool: 版本号是否符合要求
    """
    version_pattern = r"^\d+\.\d+\.\d+$"
    try:
        if not re.match(version_pattern, version):
            logger.error(f"无效的版本号格式: {version}")
            return False

        def parse_version(ver: str) -> Tuple[int, ...]:
            return tuple(map(int, ver.split(".")))

        current = parse_version(version)

        if min_version and current < parse_version(min_version):
            logger.error(f"版本号 {version} 小于最小要求 {min_version}")
            return False

        if max_version and current > parse_version(max_version):
            logger.error(f"版本号 {version} 大于最大要求 {max_version}")
            return False

        return True

    except Exception as e:
        logger.error(f"版本检查失败: {str(e)}")
        return False


def modify_main_js(main_path: str) -> bool:
    """
    修改 main.js 文件

    Args:
        main_path: main.js 文件路径

    Returns:
        bool: 修改是否成功
    """
    try:
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_file:
            with open(main_path, "r", encoding="utf-8") as main_file:
                content = main_file.read()

            # 执行替换
            patterns = {
                r"async getMachineId\(\)\{return [^??]+\?\?([^}]+)\}": r"async getMachineId(){return \1}",
                r"async getMacMachineId\(\)\{return [^??]+\?\?([^}]+)\}": r"async getMacMachineId(){return \1}",
            }

            for pattern, replacement in patterns.items():
                content = re.sub(pattern, replacement, content)

            tmp_file.write(content)
            tmp_path = tmp_file.name

        # 使用 shutil.copy2 保留文件权限
        shutil.copy2(main_path, main_path + ".old")
        shutil.move(tmp_path, main_path)
        logger.info("文件修改成功")
        return True

    except Exception as e:
        logger.error(f"修改文件时发生错误: {str(e)}")
        if "tmp_path" in locals():
            os.unlink(tmp_path)
        return False


def patch_cursor_get_machine_id() -> None:
    """主函数"""
    logger.info("开始执行脚本...")

    try:
        # 获取路径
        pkg_path, main_path = get_cursor_paths()

        # 检查系统要求
        if not check_system_requirements(pkg_path, main_path):
            sys.exit(1)

        # 获取版本号
        try:
            with open(pkg_path, "r", encoding="utf-8") as f:
                version = json.load(f)["version"]
            logger.info(f"当前 Cursor 版本: {version}")
        except Exception as e:
            logger.error(f"无法读取版本号: {str(e)}")
            sys.exit(1)

        # 检查版本
        if not version_check(version, min_version="0.45.0"):
            logger.error("版本不符合要求（需 >= 0.45.x）")
            sys.exit(1)

        logger.info("版本检查通过，准备修改文件")

        # 修改文件
        if not modify_main_js(main_path):
            sys.exit(1)

        logger.info("脚本执行完成")

    except Exception as e:
        logger.error(f"执行过程中发生错误: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    patch_cursor_get_machine_id()
