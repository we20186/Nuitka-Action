# -*- coding: utf-8 -*-
"""
笔记本高清视频修复 2025 V7.0 - 后期处理专版
============================================
✅ 【全新UI】仿Video2X风格界面
✅ 【任务列表】多任务管理，队列式处理
✅ 【可折叠日志】右侧日志面板可收缩
✅ 【新建任务对话框】统一的任务配置界面
✅ 【H.264编码】更好的视频兼容性
============================================

专业8步修复流程：
1. 伪影移除 - 去块、去色带
2. 预锐化+回调 - 边缘增强（自动回调）
3. 反锯齿 + 边缘精修
4. 去噪
5. 人脸修复
6. 毛发保护
7. 最终轻锐化
8. 轻微加颗粒（可选）
"""

import os, sys, subprocess, threading, cv2, numpy as np, hashlib, time, shutil, tempfile
import urllib.request, zipfile, ssl, json, glob, uuid
from datetime import date
from tkinter import (Label, Button, Text, filedialog, ttk, messagebox, Frame, 
                     BooleanVar, Checkbutton, StringVar, END, Toplevel, Canvas, 
                     LabelFrame, Entry, Scrollbar, VERTICAL, RIGHT, Y, BOTH, LEFT,
                     DISABLED, NORMAL, Scale, HORIZONTAL, DoubleVar, IntVar,
                     Listbox, SINGLE, TOP, BOTTOM, X, W, E, N, S, NW, NE, SW, SE,
                     CENTER, RIDGE, GROOVE, SUNKEN, RAISED, FLAT)
from tkinter.ttk import Progressbar, Style, Treeview, Separator
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image, ImageTk
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


# ==================== 0. 智能路径管理 ====================
class PathManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._init_paths()
    
    def _init_paths(self):
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        possible_bases = [
            self.app_dir,
            os.path.join(self.app_dir, "ide2025"),
            os.path.join(os.path.expanduser("~"), "ide2025"),
            r"C:\ide2025",
            os.path.join(os.environ.get('LOCALAPPDATA', ''), "ide2025"),
        ]
        
        self.base_dir = self._select_best_base(possible_bases)
        # 修改：将tools_dir改为fongzhuang文件夹
        self.tools_dir = os.path.join(self.base_dir, "fongzhuang")
        self.temp_dir = os.path.join(self.base_dir, "temp")
        self.output_dir = os.path.join(self.base_dir, "output")
        self.config_file = os.path.join(self.base_dir, "config.json")
        
        for d in [self.base_dir, self.tools_dir, self.temp_dir, self.output_dir]:
            self._safe_makedirs(d)
        
        self.exes = {}
        self._scan_ffmpeg()
        self._save_config()

    def _select_best_base(self, candidates):
        for path in candidates:
            if path and os.path.exists(os.path.join(path, "tools")):
                return path
        for path in candidates:
            if path and self._is_writable(path):
                return path
        return self.app_dir
    
    def _is_writable(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except:
            return False
    
    def _safe_makedirs(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            return True
        except:
            return False
    
    def _scan_ffmpeg(self):
        """扫描ffmpeg"""
        exe_targets = {"ffmpeg": ["ffmpeg.exe"], "ffprobe": ["ffprobe.exe"]}
        search_roots = [self.tools_dir, self.base_dir, self.app_dir]
        
        for key, names in exe_targets.items():
            found_path = None
            for root in search_roots:
                if not os.path.exists(root):
                    continue
                for name in names:
                    direct_path = os.path.join(root, name)
                    if os.path.isfile(direct_path) and self._verify_exe_file(direct_path):
                        found_path = direct_path
                        break
                if found_path:
                    break
            
            if not found_path:
                found_path = self._find_in_system_path(key)
            
            self.exes[key] = found_path if found_path else os.path.join(self.tools_dir, names[0])
    
    def _verify_exe_file(self, path):
        try:
            if not os.path.isfile(path) or os.path.getsize(path) < 10000:
                return False
            with open(path, 'rb') as f:
                return f.read(2) == b'MZ'
        except:
            return False
    
    def _find_in_system_path(self, name):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(['where', name], capture_output=True, startupinfo=si, timeout=5)
            if result.returncode == 0:
                path = result.stdout.decode().strip().split('\n')[0].strip()
                if os.path.isfile(path):
                    return path
        except:
            pass
        return None
    
    def _save_config(self):
        try:
            config = {"base_dir": self.base_dir, "tools_dir": self.tools_dir,
                      "exes": self.exes, "last_update": time.strftime("%Y-%m-%d %H:%M:%S")}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except:
            pass
    
    def get_exe(self, name):
        return self.exes.get(name, "")
    
    def is_exe_available(self, name):
        path = self.exes.get(name, "")
        return path and os.path.isfile(path) and self._verify_exe_file(path)
    
    def refresh(self):
        self._initialized = False
        self.__init__()
    
    def get_info(self):
        info = {"程序目录": self.app_dir, "工作目录": self.base_dir, "工具目录": self.tools_dir}
        path = self.exes.get("ffmpeg", "")
        info["ffmpeg"] = f"✓ {path}" if path and os.path.isfile(path) else f"✗ 未找到"
        return info


PM = PathManager()


# ==================== 1. 授权验证 ====================
LICENSE_FILE_NAME = "license.key"
MAGIC_VALUE = "788990"

class LicenseManager:
    @staticmethod
    def _get_license_path():
        return os.path.join(PM.tools_dir, LICENSE_FILE_NAME)
    
    @staticmethod
    def get_machine_code():
        raw = ""
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            try:
                ps_cmd = '(Get-CimInstance Win32_Processor).ProcessorId + (Get-CimInstance Win32_BaseBoard).SerialNumber'
                result = subprocess.check_output(['powershell', '-Command', ps_cmd],
                    startupinfo=si, timeout=15, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore').strip()
                if result and len(result) > 5:
                    raw = result.replace(" ", "").replace("\n", "")
            except:
                pass
            if len(raw) < 5:
                try:
                    result = subprocess.check_output('wmic cpu get processorid', shell=True,
                        startupinfo=si, timeout=10, stderr=subprocess.DEVNULL).decode('gbk', errors='ignore')
                    lines = [l.strip() for l in result.split('\n') if l.strip() and 'ProcessorId' not in l]
                    if lines:
                        raw = lines[0].replace(" ", "")
                except:
                    pass
            if len(raw) < 5:
                import uuid as uuid_mod
                raw = str(uuid_mod.getnode())
        except:
            import uuid as uuid_mod
            raw = str(uuid_mod.getnode())
        h = hashlib.md5(raw.encode()).hexdigest().upper()
        return f"{h[0:4]}-{h[4:8]}-{h[8:12]}-{h[12:16]}"
    
    @staticmethod
    def verify_key(machine_code, input_key):
        try:
            clean = machine_code.replace("-", "").replace(" ", "")
            today = date.today().strftime("%Y%m%d")
            sha = hashlib.sha256(f"{clean}{today}{MAGIC_VALUE}".encode()).hexdigest().upper()
            correct = "-".join([sha[i:i+5] for i in range(0, 25, 5)])
            return input_key.strip().upper() == correct
        except:
            return False
    
    @staticmethod
    def check_license_file():
        path = LicenseManager._get_license_path()
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r") as f:
                saved = f.read().strip()
            return saved == hashlib.md5(LicenseManager.get_machine_code().encode()).hexdigest()
        except:
            return False
    
    @staticmethod
    def save_license():
        try:
            path = LicenseManager._get_license_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(hashlib.md5(LicenseManager.get_machine_code().encode()).hexdigest())
            return True
        except:
            return False


# ==================== 2. 稳定下载器 (仅FFmpeg) ====================
class RobustDownloader:
    MIRRORS = {
        "ffmpeg": [
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
            "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        ],
    }
    
    DESCRIPTIONS = {"ffmpeg": "FFmpeg (音视频处理)"}
    
    def __init__(self, log_func=print):
        self.log = log_func
        self._create_ssl_context()
    
    def _create_ssl_context(self):
        try:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        except:
            self.ssl_context = None
    
    def download_with_retry(self, url, dest_path, max_retries=3, timeout=120, progress_cb=None):
        last_error = None
        for attempt in range(max_retries):
            try:
                self.log(f"  尝试 {attempt + 1}/{max_retries}: {url[:70]}...")
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*', 'Connection': 'keep-alive',
                })
                opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=self.ssl_context))
                with opener.open(req, timeout=timeout) as response:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    temp_path = dest_path + ".tmp"
                    with open(temp_path, 'wb') as f:
                        while True:
                            chunk = response.read(65536)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_cb and total_size > 0:
                                progress_cb(downloaded / total_size * 100)
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    os.rename(temp_path, dest_path)
                    file_size = os.path.getsize(dest_path)
                    if file_size < 100000:
                        raise Exception(f"文件太小({file_size}字节)")
                    self.log(f"  ✓ 下载完成 ({file_size / 1024 / 1024:.1f}MB)")
                    return True
            except Exception as e:
                last_error = e
                self.log(f"  ⚠️ 失败: {str(e)[:60]}")
                if os.path.exists(dest_path + ".tmp"):
                    try:
                        os.remove(dest_path + ".tmp")
                    except:
                        pass
                if attempt < max_retries - 1:
                    time.sleep(3 * (attempt + 1))
        return False
    
    def download_component(self, key, progress_cb=None):
        if key not in self.MIRRORS:
            return False
        mirrors = self.MIRRORS[key]
        desc = self.DESCRIPTIONS.get(key, key)
        self.log(f"\n{'='*50}\n📥 开始下载 {desc}\n{'='*50}")
        
        zip_path = os.path.join(PM.temp_dir, f"{key}_{int(time.time())}.zip")
        os.makedirs(PM.temp_dir, exist_ok=True)
        
        success = False
        for i, url in enumerate(mirrors):
            self.log(f"\n📡 镜像源 {i + 1}/{len(mirrors)}")
            if self.download_with_retry(url, zip_path, max_retries=2, timeout=180, progress_cb=progress_cb):
                success = True
                break
        
        if not success:
            return False
        
        try:
            self.log(f"\n📦 解压并安装...")
            result = self._extract_and_install(zip_path, key)
            if result:
                PM.refresh()
                if PM.is_exe_available(key):
                    self.log(f"✅ {desc} 安装成功!")
                    return True
            return False
        except Exception as e:
            self.log(f"❌ 解压失败: {e}")
            return False
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except:
                    pass
    
    def _extract_and_install(self, zip_path, key):
        extract_dir = os.path.join(PM.temp_dir, f"extract_{key}_{int(time.time())}")
        try:
            if os.path.exists(extract_dir):
                shutil.rmtree(extract_dir)
            os.makedirs(extract_dir)
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(extract_dir)
            
            installed_count = 0
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    if f.endswith('.exe'):
                        src = os.path.join(root, f)
                        dst = os.path.join(PM.tools_dir, f)
                        try:
                            if os.path.exists(dst):
                                os.remove(dst)
                            shutil.copy2(src, dst)
                            installed_count += 1
                        except:
                            pass
            return installed_count > 0
        except:
            return False
        finally:
            if os.path.exists(extract_dir):
                try:
                    shutil.rmtree(extract_dir)
                except:
                    pass


# ==================== 3. 环境检查器 ====================
class EnvironmentChecker:
    def __init__(self, log_func=print):
        self.log = log_func
    
    def check_all(self):
        PM.refresh()
        results = {"ffmpeg": False, "ffmpeg_path": "", "details": {}}
        
        ffmpeg_status = self._check_ffmpeg()
        results["ffmpeg"] = ffmpeg_status["available"]
        results["ffmpeg_path"] = ffmpeg_status["path"]
        results["details"]["FFmpeg"] = ffmpeg_status
        
        return results
    
    def _check_ffmpeg(self):
        status = {"name": "FFmpeg", "available": False, "path": "", "reason": ""}
        ffmpeg_path = PM.get_exe("ffmpeg")
        if ffmpeg_path and os.path.isfile(ffmpeg_path):
            status["path"] = ffmpeg_path
            status["available"] = True
            status["reason"] = "正常"
            return status
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, startupinfo=si, timeout=10)
            if result.returncode == 0:
                status["available"] = True
                status["path"] = "系统PATH"
                status["reason"] = "系统PATH中找到"
                return status
        except:
            pass
        status["reason"] = "未找到ffmpeg"
        return status
    
    def get_report(self):
        r = self.check_all()
        lines = ["=" * 65, "📦 环境检测报告", "=" * 65, "",
                 "📁 【目录配置】", f"  工具目录: {PM.tools_dir}", ""]
        icon = "✅" if r["ffmpeg"] else "❌"
        lines.append(f"  {icon} FFmpeg: {r['details'].get('FFmpeg', {}).get('reason', '')}")
        lines.extend(["", "=" * 65])
        return "\n".join(lines)


# ==================== 4. GPU检测 ====================
class GPUDetector:
    def __init__(self):
        self.info = self._detect()
    
    def _detect(self):
        info = {"has_discrete": False, "has_integrated": False, "name": "未检测到", 
                "vendor": "unknown", "memory_mb": 0, "cores": 0, "display_name": "CPU模式"}
        gpu_list = self._try_powershell() or self._try_wmic() or []
        for gpu in gpu_list:
            name = gpu.get("name", "")
            upper = name.upper()
            if any(k in upper for k in ['NVIDIA', 'GEFORCE', 'RTX', 'GTX', 'AMD', 'RADEON', 'RX']):
                info["has_discrete"] = True
                info["name"] = name[:50]
                info["vendor"] = "nvidia" if any(k in upper for k in ['NVIDIA', 'GEFORCE', 'RTX', 'GTX']) else "amd"
                info["memory_mb"] = gpu.get("memory", 0)
                info["display_name"] = name[:40]
                break
            elif any(k in upper for k in ['INTEL', 'UHD', 'IRIS', 'HD GRAPHICS']):
                info["has_integrated"] = True
                if not info["has_discrete"]:
                    info["name"] = name[:50]
                    info["vendor"] = "intel"
                    info["display_name"] = name[:40]
        
        try:
            info["cores"] = os.cpu_count() or 4
        except:
            info["cores"] = 4
        
        return info
    
    def _try_powershell(self):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            ps_cmd = '''Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + "|" + $_.AdapterRAM }'''
            result = subprocess.check_output(['powershell', '-Command', ps_cmd],
                startupinfo=si, timeout=15, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
            gpu_list = []
            for line in result.strip().split('\n'):
                if '|' in line:
                    parts = line.split('|')
                    name = parts[0].strip()
                    try:
                        mem = int(parts[1].strip()) // (1024*1024) if len(parts) > 1 and parts[1].strip().isdigit() else 0
                    except:
                        mem = 0
                    if name:
                        gpu_list.append({"name": name, "memory": mem})
            return gpu_list if gpu_list else None
        except:
            return None
    
    def _try_wmic(self):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.check_output('wmic path win32_VideoController get name',
                startupinfo=si, shell=True, timeout=10, stderr=subprocess.DEVNULL).decode('gbk', errors='ignore')
            gpu_list = []
            for line in result.split('\n'):
                line = line.strip()
                if line and 'Name' not in line:
                    gpu_list.append({"name": line, "memory": 0})
            return gpu_list if gpu_list else None
        except:
            return None
    
    def get_status(self):
        i = self.info
        if i["has_discrete"]:
            icon = "🟢" if i["vendor"] == "nvidia" else "🔴"
            mem = f" ({i['memory_mb']}MB)" if i['memory_mb'] > 0 else ""
            return f"{icon} {i['name']}{mem}"
        elif i["has_integrated"]:
            return f"🔵 {i['name']}"
        return "⚙️ CPU模式"
    
    def get_short_status(self):
        """获取简短的GPU状态用于标题栏显示"""
        i = self.info
        if i["has_discrete"]:
            return i['name'][:30]
        elif i["has_integrated"]:
            return i['name'][:30]
        return "CPU模式"
    
    def get_cores(self):
        return self.info.get("cores", 4)


# ==================== 5. 任务状态枚举 ====================
class TaskStatus(Enum):
    PENDING = "pending"      # 等待处理
    RUNNING = "running"      # 正在处理
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    STOPPED = "stopped"      # 已停止


# ==================== 6. 任务数据类 ====================
@dataclass
class TaskItem:
    """任务项数据类"""
    task_id: str
    input_path: str
    output_path: str
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    current_frame: int = 0
    total_frames: int = 0
    
    # 处理配置
    use_detail_restore: bool = False
    detail_intensity: str = "medium"
    detail_opts: Dict[str, bool] = field(default_factory=dict)
    
    use_basic: bool = False
    basic_intensity: str = "medium"
    basic_opts: Dict[str, bool] = field(default_factory=dict)
    filter_opts: Dict[str, bool] = field(default_factory=dict)
    
    use_advanced: bool = False
    adv_intensity: str = "medium"
    smart_mode: bool = True
    adv_opts: Dict[str, bool] = field(default_factory=dict)
    
    # 时间统计
    start_time: float = 0.0
    elapsed_time: float = 0.0
    fps: float = 0.0
    
    def get_filename(self) -> str:
        return os.path.basename(self.input_path)
    
    def get_process_types(self) -> str:
        """获取处理类型描述"""
        types = []
        if self.use_detail_restore:
            types.append("细节修复")
        if self.use_basic:
            types.append("智能后期")
        if self.use_advanced:
            types.append("高级后期")
        return ", ".join(types) if types else "无处理"
    
    def get_progress_text(self) -> str:
        if self.status == TaskStatus.PENDING:
            return "尚未处理"
        elif self.status == TaskStatus.RUNNING:
            return f"{self.current_frame}/{self.total_frames} ({self.progress:.0f}%)"
        elif self.status == TaskStatus.COMPLETED:
            return f"{self.total_frames}/{self.total_frames} (100%)"
        elif self.status == TaskStatus.PAUSED:
            return f"已暂停 {self.progress:.0f}%"
        elif self.status == TaskStatus.STOPPED:
            return "已停止"
        elif self.status == TaskStatus.FAILED:
            return "处理失败"
        return ""
    
    def get_config(self) -> Dict[str, Any]:
        """获取完整配置字典"""
        cfg = {
            "use_detail_restore": self.use_detail_restore,
            "detail_intensity": self.detail_intensity,
            "use_basic": self.use_basic,
            "basic_intensity": self.basic_intensity,
            "use_advanced": self.use_advanced,
            "adv_intensity": self.adv_intensity,
            "smart_mode": self.smart_mode,
        }
        cfg.update(self.detail_opts)
        cfg.update(self.basic_opts)
        cfg.update(self.filter_opts)
        cfg.update(self.adv_opts)
        return cfg


# ==================== 7. 任务管理器 ====================
class TaskManager:
    """任务管理器 - 管理所有处理任务"""
    
    def __init__(self):
        self.tasks: Dict[str, TaskItem] = {}
        self.task_order: List[str] = []  # 保持任务顺序
        self.current_task_id: Optional[str] = None
        self._lock = threading.Lock()
    
    def add_task(self, task: TaskItem) -> str:
        """添加任务"""
        with self._lock:
            self.tasks[task.task_id] = task
            self.task_order.append(task.task_id)
        return task.task_id
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务"""
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                self.task_order.remove(task_id)
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[TaskItem]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskItem]:
        """按顺序获取所有任务"""
        return [self.tasks[tid] for tid in self.task_order if tid in self.tasks]
    
    def get_pending_tasks(self) -> List[TaskItem]:
        """获取待处理任务"""
        return [t for t in self.get_all_tasks() if t.status == TaskStatus.PENDING]
    
    def get_next_task(self) -> Optional[TaskItem]:
        """获取下一个待处理任务"""
        for tid in self.task_order:
            task = self.tasks.get(tid)
            if task and task.status == TaskStatus.PENDING:
                return task
        return None
    
    def update_task(self, task_id: str, **kwargs):
        """更新任务属性"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task:
                for key, value in kwargs.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
    
    def clear_all(self):
        """清除所有任务"""
        with self._lock:
            self.tasks.clear()
            self.task_order.clear()
            self.current_task_id = None
    
    def get_task_count(self) -> int:
        """获取任务数量"""
        return len(self.tasks)
    
    def get_completed_count(self) -> int:
        """获取已完成任务数量"""
        return sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)


# ==================== 8. 智能图像分析器 ====================
class ImageAnalyzer:
    """智能分析图像质量，决定是否需要处理"""
    
    THRESHOLDS = {
        "brightness": {"low": 80, "high": 180, "optimal_low": 100, "optimal_high": 160},
        "contrast": {"low": 30, "high": 80, "optimal": 50},
        "saturation": {"low": 40, "high": 180, "optimal": 100},
        "sharpness": {"low": 100, "high": 800, "optimal": 300},
        "noise": {"low": 5, "high": 30, "optimal": 15},
        "block_artifact": {"low": 10, "high": 50, "optimal": 20},
        "aliasing": {"low": 0.1, "high": 0.4, "optimal": 0.2},
    }
    
    @staticmethod
    def analyze(img):
        """分析图像，返回各项指标"""
        if img is None:
            return {}
        
        metrics = {}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        metrics["brightness"] = np.mean(gray)
        metrics["brightness_std"] = np.std(gray)
        metrics["contrast"] = np.std(gray)
        
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        metrics["saturation"] = np.mean(hsv[:,:,1])
        
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        metrics["sharpness"] = laplacian.var()
        metrics["noise"] = ImageAnalyzer._estimate_noise(gray)
        
        b, g, r = cv2.split(img)
        metrics["color_temp"] = np.mean(r.astype(float) - b.astype(float))
        metrics["highlight_ratio"] = np.sum(gray > 240) / gray.size
        metrics["shadow_ratio"] = np.sum(gray < 15) / gray.size
        metrics["block_artifact"] = ImageAnalyzer._estimate_block_artifact(gray)
        metrics["aliasing"] = ImageAnalyzer._estimate_aliasing(gray)
        
        return metrics
    
    @staticmethod
    def _estimate_noise(gray):
        try:
            kernel = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]])
            filtered = cv2.filter2D(gray, -1, kernel)
            noise = np.median(np.abs(filtered)) / 0.6745
            return noise
        except:
            return 10
    
    @staticmethod
    def _estimate_block_artifact(gray):
        try:
            h, w = gray.shape
            block_size = 8
            h_diff = 0
            v_diff = 0
            count = 0
            
            for y in range(0, h - block_size, block_size):
                for x in range(block_size, w - block_size, block_size):
                    left = float(gray[y, x-1])
                    right = float(gray[y, x])
                    h_diff += abs(left - right)
                    count += 1
            
            for y in range(block_size, h - block_size, block_size):
                for x in range(0, w - block_size, block_size):
                    top = float(gray[y-1, x])
                    bottom = float(gray[y, x])
                    v_diff += abs(top - bottom)
                    count += 1
            
            if count > 0:
                block_score = (h_diff + v_diff) / count
            else:
                block_score = 0
            
            return block_score
        except:
            return 20
    
    @staticmethod
    def _estimate_aliasing(gray):
        try:
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            edge_mag = np.sqrt(sobelx**2 + sobely**2)
            edge_dir = np.arctan2(sobely, sobelx)
            
            dir_diff_x = np.abs(np.diff(edge_dir, axis=1))
            dir_diff_y = np.abs(np.diff(edge_dir, axis=0))
            
            edge_mask = edge_mag > 30
            edge_mask_x = edge_mask[:, :-1]
            edge_mask_y = edge_mask[:-1, :]
            
            aliasing_x = np.mean(dir_diff_x[edge_mask_x]) if np.sum(edge_mask_x) > 0 else 0
            aliasing_y = np.mean(dir_diff_y[edge_mask_y]) if np.sum(edge_mask_y) > 0 else 0
            
            aliasing_score = (aliasing_x + aliasing_y) / 2
            return min(aliasing_score, 1.0)
        except:
            return 0.2
    
    @staticmethod
    def get_recommendations(metrics):
        """根据分析结果，返回处理建议"""
        recommendations = {}
        th = ImageAnalyzer.THRESHOLDS
        
        brightness = metrics.get("brightness", 128)
        if brightness < th["brightness"]["low"]:
            recommendations["opt_bright"] = {"need": True, "reason": f"亮度过低({brightness:.0f})"}
        elif brightness > th["brightness"]["high"]:
            recommendations["opt_bright"] = {"need": False, "reason": f"亮度已足够", "skip": True}
        else:
            recommendations["opt_bright"] = {"need": False, "reason": f"亮度正常"}
        
        contrast = metrics.get("contrast", 50)
        if contrast < th["contrast"]["low"]:
            recommendations["opt_contrast"] = {"need": True, "reason": f"对比度过低({contrast:.0f})"}
        elif contrast > th["contrast"]["high"]:
            recommendations["opt_contrast"] = {"need": False, "reason": f"对比度已足够", "skip": True}
        else:
            recommendations["opt_contrast"] = {"need": False, "reason": f"对比度正常"}
        
        saturation = metrics.get("saturation", 100)
        if saturation < th["saturation"]["low"]:
            recommendations["opt_sat"] = {"need": True, "reason": f"饱和度过低({saturation:.0f})"}
        elif saturation > th["saturation"]["high"]:
            recommendations["opt_sat"] = {"need": False, "reason": f"饱和度已足够", "skip": True}
        else:
            recommendations["opt_sat"] = {"need": False, "reason": f"饱和度正常"}
        
        sharpness = metrics.get("sharpness", 300)
        if sharpness < th["sharpness"]["low"]:
            recommendations["opt_sharp"] = {"need": True, "reason": f"清晰度过低({sharpness:.0f})"}
        elif sharpness > th["sharpness"]["high"]:
            recommendations["opt_sharp"] = {"need": False, "reason": f"清晰度已足够", "skip": True}
        else:
            recommendations["opt_sharp"] = {"need": False, "reason": f"清晰度正常"}
        
        noise = metrics.get("noise", 15)
        if noise > th["noise"]["high"]:
            recommendations["opt_denoise"] = {"need": True, "reason": f"噪声过高({noise:.1f})"}
        elif noise < th["noise"]["low"]:
            recommendations["opt_denoise"] = {"need": False, "reason": f"噪声很低", "skip": True}
        else:
            recommendations["opt_denoise"] = {"need": False, "reason": f"噪声正常"}
        
        block_artifact = metrics.get("block_artifact", 20)
        if block_artifact > th["block_artifact"]["high"]:
            recommendations["detail_deblock"] = {"need": True, "reason": f"块状伪影严重({block_artifact:.1f})"}
        elif block_artifact > th["block_artifact"]["optimal"]:
            recommendations["detail_deblock"] = {"need": True, "reason": f"块状伪影中等({block_artifact:.1f})"}
        else:
            recommendations["detail_deblock"] = {"need": False, "reason": f"块状伪影较少", "skip": True}
        
        aliasing = metrics.get("aliasing", 0.2)
        if aliasing > th["aliasing"]["high"]:
            recommendations["detail_aa"] = {"need": True, "reason": f"锯齿明显({aliasing:.2f})"}
        elif aliasing > th["aliasing"]["optimal"]:
            recommendations["detail_aa"] = {"need": True, "reason": f"锯齿中等({aliasing:.2f})"}
        else:
            recommendations["detail_aa"] = {"need": False, "reason": f"锯齿较少", "skip": True}
        
        return recommendations


# ==================== 9. 专业8步修复流程 ====================
class ProfessionalRestorer:
    """
    专业8步修复流程 (2025年后期处理版)
    """
    
    INTENSITY = {
        "light": {
            "deblock_strength": 0.5, "deblock_thresh": 18,
            "deband_threshold": 10, "deband_dither": 0.4,
            "pre_sharpen_contrast": 1.2, "pre_sharpen_strength": 70,
            "contrast_rollback": 0.88,
            "aa_strength": 0.6, "edge_refine": 0.5,
            "denoise_strength": 0.4, "denoise_preserve": 0.9,
            "face_strength": 0.4, "hair_protect": 0.9,
            "final_sharp": 0.4,
            "grain_strength": 2,
        },
        "medium": {
            "deblock_strength": 0.7, "deblock_thresh": 14,
            "deband_threshold": 7, "deband_dither": 0.55,
            "pre_sharpen_contrast": 1.4, "pre_sharpen_strength": 100,
            "contrast_rollback": 0.83,
            "aa_strength": 0.75, "edge_refine": 0.65,
            "denoise_strength": 0.55, "denoise_preserve": 0.82,
            "face_strength": 0.5, "hair_protect": 0.85,
            "final_sharp": 0.55,
            "grain_strength": 4,
        },
        "heavy": {
            "deblock_strength": 0.88, "deblock_thresh": 10,
            "deband_threshold": 5, "deband_dither": 0.7,
            "pre_sharpen_contrast": 1.6, "pre_sharpen_strength": 130,
            "contrast_rollback": 0.78,
            "aa_strength": 0.9, "edge_refine": 0.8,
            "denoise_strength": 0.72, "denoise_preserve": 0.72,
            "face_strength": 0.6, "hair_protect": 0.78,
            "final_sharp": 0.7,
            "grain_strength": 6,
        },
    }
    
    _frame_buffer = []
    _max_buffer_size = 3
    _face_cascade = None
    _face_cascade_loaded = False
    
    @classmethod
    def _load_face_cascade(cls):
        if cls._face_cascade_loaded:
            return cls._face_cascade
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            cls._face_cascade = cv2.CascadeClassifier(cascade_path)
            if cls._face_cascade.empty():
                cls._face_cascade = None
        except:
            cls._face_cascade = None
        cls._face_cascade_loaded = True
        return cls._face_cascade
    
    @staticmethod
    def detect_faces(img):
        cascade = ProfessionalRestorer._load_face_cascade()
        if cascade is None:
            return []
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5,
                                             minSize=(30, 30), flags=cv2.CASCADE_SCALE_IMAGE)
            return faces.tolist() if len(faces) > 0 else []
        except:
            return []
    
    @staticmethod
    def guided_filter(I, p, r, eps):
        """引导滤波 - 边缘感知平滑"""
        try:
            I = I.astype(np.float64)
            p = p.astype(np.float64)
            mean_I = cv2.boxFilter(I, -1, (r, r))
            mean_p = cv2.boxFilter(p, -1, (r, r))
            mean_Ip = cv2.boxFilter(I * p, -1, (r, r))
            cov_Ip = mean_Ip - mean_I * mean_p
            mean_II = cv2.boxFilter(I * I, -1, (r, r))
            var_I = mean_II - mean_I * mean_I
            a = cov_Ip / (var_I + eps)
            b = mean_p - a * mean_I
            mean_a = cv2.boxFilter(a, -1, (r, r))
            mean_b = cv2.boxFilter(b, -1, (r, r))
            q = mean_a * I + mean_b
            return q
        except:
            return p
    
    @staticmethod
    def step1_artifact_removal(img, intensity="medium"):
        """步骤1: 伪影移除 - 去块、去色带"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        try:
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            
            edges = cv2.Canny(gray.astype(np.uint8), 45, 110)
            edge_protect = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)
            edge_protect_mask = 1 - edge_protect.astype(np.float32) / 255.0
            
            block_mask = np.zeros((h, w), dtype=np.float32)
            thresh = cfg["deblock_thresh"]
            
            for block_size in [8, 16]:
                for x in range(block_size, w - 1, block_size):
                    if x >= w - 1:
                        continue
                    left = gray[:, x-1]
                    right = gray[:, x]
                    diff = np.abs(left - right)
                    boundary = ((diff > 1.5) & (diff < thresh)).astype(np.float32)
                    for dx in range(-2, 3):
                        if 0 <= x + dx < w:
                            weight = 1.0 - abs(dx) * 0.2
                            block_mask[:, x + dx] = np.maximum(block_mask[:, x + dx], boundary * weight)
                
                for y in range(block_size, h - 1, block_size):
                    if y >= h - 1:
                        continue
                    top = gray[y-1, :]
                    bottom = gray[y, :]
                    diff = np.abs(top - bottom)
                    boundary = ((diff > 1.5) & (diff < thresh)).astype(np.float32)
                    for dy in range(-2, 3):
                        if 0 <= y + dy < h:
                            weight = 1.0 - abs(dy) * 0.2
                            block_mask[y + dy, :] = np.maximum(block_mask[y + dy, :], boundary * weight)
            
            block_mask = block_mask * edge_protect_mask
            block_mask = cv2.GaussianBlur(block_mask, (5, 5), 1.0)
            
            strength = cfg["deblock_strength"]
            gray_guide = gray / 255.0
            smooth = np.zeros_like(img, dtype=np.float64)
            for c in range(3):
                channel = img[:, :, c].astype(np.float64) / 255.0
                smooth[:, :, c] = ProfessionalRestorer.guided_filter(gray_guide, channel, 5, 0.01) * 255.0
            smooth = np.clip(smooth, 0, 255).astype(np.uint8)
            
            block_mask_3ch = np.stack([block_mask] * 3, axis=-1)
            result = img.astype(np.float32) * (1 - block_mask_3ch * strength) + \
                     smooth.astype(np.float32) * (block_mask_3ch * strength)
            result = np.clip(result, 0, 255).astype(np.uint8)
            
            deband_thresh = cfg["deband_threshold"]
            dither = cfg["deband_dither"]
            
            local_var = cv2.blur(gray**2, (9, 9)) - cv2.blur(gray, (9, 9))**2
            local_var = np.sqrt(np.maximum(local_var, 0))
            banding_mask = (local_var < deband_thresh).astype(np.float32)
            banding_mask = banding_mask * edge_protect_mask
            banding_mask = cv2.GaussianBlur(banding_mask, (11, 11), 2.5)
            
            result_f = result.astype(np.float32)
            for c in range(3):
                channel = result_f[:, :, c]
                smoothed = cv2.GaussianBlur(channel, (15, 15), 3.0)
                noise = np.random.normal(0, dither, channel.shape).astype(np.float32)
                smoothed = smoothed + noise
                result_f[:, :, c] = channel * (1 - banding_mask * 0.65) + smoothed * (banding_mask * 0.65)
            
            return np.clip(result_f, 0, 255).astype(np.uint8)
        except:
            return img
    
    @staticmethod
    def step2_presharpen_with_rollback(img, intensity="medium", metrics=None):
        """步骤2: 预锐化+回调"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        contrast_factor = cfg["pre_sharpen_contrast"]
        rollback = cfg["contrast_rollback"]
        
        if metrics:
            src_contrast = metrics.get("contrast", 50)
            if src_contrast > 60:
                contrast_factor = 1.0 + (contrast_factor - 1.0) * 0.5
                rollback = 1.0 - (1.0 - rollback) * 0.5
        
        try:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
            l_channel = lab[:, :, 0]
            mid = 128
            l_enhanced = mid + (l_channel - mid) * contrast_factor
            l_enhanced = np.clip(l_enhanced, 0, 255)
            lab[:, :, 0] = l_enhanced
            result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
            
            strength = cfg["pre_sharpen_strength"] / 100.0
            blur = cv2.GaussianBlur(result, (0, 0), 2.0)
            result = cv2.addWeighted(result, 1 + strength, blur, -strength, 0)
            
            lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB).astype(np.float32)
            l_channel = lab[:, :, 0]
            l_adjusted = mid + (l_channel - mid) * rollback
            lab[:, :, 0] = np.clip(l_adjusted, 0, 255)
            result = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)
            
            return result
        except:
            return img
    
    @staticmethod
    def step3_antialiasing(img, intensity="medium"):
        """步骤3: 反锯齿 + 边缘精修"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        try:
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float64)
            
            sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_mag = np.sqrt(sobel_x**2 + sobel_y**2)
            gradient_dir = np.arctan2(sobel_y, sobel_x)
            edge_strength = np.clip(gradient_mag / 80.0, 0, 1)
            
            diff_h = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
            diff_v = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
            step_thresh = 8
            jagged_h = (diff_h > step_thresh).astype(np.float64) * edge_strength
            jagged_v = (diff_v > step_thresh).astype(np.float64) * edge_strength
            
            abs_dir = np.abs(gradient_dir)
            near_horizontal = ((abs_dir < 0.3) | (abs_dir > np.pi - 0.3)).astype(np.float64)
            near_vertical = (np.abs(abs_dir - np.pi/2) < 0.3).astype(np.float64)
            
            result = img.astype(np.float64)
            aa_strength = cfg["aa_strength"]
            
            h_mask = jagged_v * near_horizontal
            if np.sum(h_mask) > 100:
                v_kernel = np.array([[0.15], [0.20], [0.30], [0.20], [0.15]])
                v_interp = cv2.filter2D(result, -1, v_kernel)
                h_mask_3ch = np.stack([h_mask] * 3, axis=-1)
                result = result + (v_interp - result) * h_mask_3ch * aa_strength * 0.5
            
            v_mask = jagged_h * near_vertical
            if np.sum(v_mask) > 100:
                h_kernel = np.array([[0.15, 0.20, 0.30, 0.20, 0.15]])
                h_interp = cv2.filter2D(result, -1, h_kernel)
                v_mask_3ch = np.stack([v_mask] * 3, axis=-1)
                result = result + (h_interp - result) * v_mask_3ch * aa_strength * 0.5
            
            edge_refine = cfg["edge_refine"]
            edge_region = (edge_strength > 0.2).astype(np.float64)
            edge_region = cv2.GaussianBlur(edge_region, (3, 3), 0.5)
            
            tangent_smooth = cv2.GaussianBlur(result, (3, 3), 0.5)
            edge_3ch = np.stack([edge_region] * 3, axis=-1)
            result = result * (1 - edge_3ch * edge_refine * 0.15) + \
                    tangent_smooth * (edge_3ch * edge_refine * 0.15)
            
            return np.clip(result, 0, 255).astype(np.uint8)
        except:
            return img
    
    @staticmethod
    def step4_denoise(img, intensity="medium", metrics=None):
        """步骤4: 去噪"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        try:
            strength = cfg["denoise_strength"]
            preserve = cfg["denoise_preserve"]
            
            denoised = cv2.bilateralFilter(img, 9, 45, 45)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            local_var = cv2.blur(gray**2, (7, 7)) - cv2.blur(gray, (7, 7))**2
            local_var = np.sqrt(np.maximum(local_var, 0))
            texture_mask = (local_var > 12).astype(np.float32)
            texture_mask = cv2.GaussianBlur(texture_mask, (5, 5), 1.0)
            
            denoise_mask = (1 - texture_mask * preserve) * strength
            denoise_mask_3ch = np.stack([denoise_mask] * 3, axis=-1)
            
            result = img.astype(np.float32) * (1 - denoise_mask_3ch) + \
                    denoised.astype(np.float32) * denoise_mask_3ch
            
            return np.clip(result, 0, 255).astype(np.uint8)
        except:
            return img
    
    @staticmethod
    def step5_face_repair(img, intensity="medium"):
        """步骤5: 人脸修复"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        faces = ProfessionalRestorer.detect_faces(img)
        if not faces:
            return img
        
        result = img.copy()
        
        try:
            for (x, y, fw, fh) in faces:
                padding = int(max(fw, fh) * 0.2)
                x1, y1 = max(0, x - padding), max(0, y - padding)
                x2, y2 = min(img.shape[1], x + fw + padding), min(img.shape[0], y + fh + padding)
                
                face_region = result[y1:y2, x1:x2].copy()
                
                face_f = face_region.astype(np.float64)
                low_freq = cv2.GaussianBlur(face_f, (0, 0), 2.0)
                high_freq = face_f - low_freq
                
                low_smooth = cv2.bilateralFilter(low_freq.astype(np.uint8), 7, 35, 35)
                
                high_preserve = 1 - cfg["face_strength"] * 0.3
                face_result = low_smooth.astype(np.float64) + high_freq * high_preserve
                face_result = np.clip(face_result, 0, 255).astype(np.uint8)
                
                hsv = cv2.cvtColor(face_region, cv2.COLOR_BGR2HSV)
                skin_mask = cv2.inRange(hsv, np.array([0, 20, 70]), np.array([20, 255, 255]))
                skin_mask = cv2.GaussianBlur(skin_mask, (15, 15), 3.0)
                skin_mask = skin_mask.astype(np.float32) / 255.0 * cfg["face_strength"]
                skin_mask_3ch = np.stack([skin_mask] * 3, axis=-1)
                
                border = int(min(y2-y1, x2-x1) * 0.15)
                transition = np.ones((y2-y1, x2-x1), dtype=np.float32)
                for i in range(border):
                    factor = i / border
                    transition[i, :] *= factor
                    transition[-(i+1), :] *= factor
                    transition[:, i] *= factor
                    transition[:, -(i+1)] *= factor
                transition_3ch = np.stack([transition] * 3, axis=-1)
                
                face_blended = face_region.astype(np.float32) * (1 - skin_mask_3ch) + \
                              face_result.astype(np.float32) * skin_mask_3ch
                
                final_blend = result[y1:y2, x1:x2].astype(np.float32) * (1 - transition_3ch) + \
                             face_blended * transition_3ch
                result[y1:y2, x1:x2] = np.clip(final_blend, 0, 255).astype(np.uint8)
            
            return result
        except:
            return img
    
    @staticmethod
    def step6_hair_protect(img, original, intensity="medium"):
        """步骤6: 毛发保护"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        faces = ProfessionalRestorer.detect_faces(img)
        if not faces:
            return img
        
        result = img.copy()
        
        try:
            h, w = result.shape[:2]
            hair_mask = np.zeros((h, w), dtype=np.float32)
            
            for (x, y, fw, fh) in faces:
                hair_top = max(0, y - int(fh * 1.2))
                hair_bottom = y + int(fh * 0.1)
                hair_left = max(0, x - int(fw * 0.25))
                hair_right = min(w, x + fw + int(fw * 0.25))
                hair_mask[hair_top:hair_bottom, hair_left:hair_right] = 1.0
            
            hair_mask = cv2.GaussianBlur(hair_mask, (15, 15), 4.0)
            
            sigma = 1.2
            blur = cv2.GaussianBlur(original, (0, 0), sigma)
            hair_detail = original.astype(np.float32) - blur.astype(np.float32)
            
            hair_protect = cfg["hair_protect"]
            hair_mask_3ch = np.stack([hair_mask] * 3, axis=-1)
            result = result.astype(np.float32) + hair_detail * hair_mask_3ch * hair_protect * 0.4
            
            return np.clip(result, 0, 255).astype(np.uint8)
        except:
            return img
    
    @staticmethod
    def step7_final_sharpen(img, intensity="medium", metrics=None):
        """步骤7: 最终轻锐化"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        if metrics:
            sharpness = metrics.get("sharpness", 300)
            if sharpness > 600:
                return img
        
        try:
            strength = cfg["final_sharp"] * 0.4
            
            blur = cv2.GaussianBlur(img, (0, 0), 1.0)
            diff = img.astype(np.float64) - blur.astype(np.float64)
            
            max_diff = 15
            diff_limited = np.tanh(diff / max_diff) * max_diff
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
            sobel_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            sobel_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            gradient = np.sqrt(sobel_x**2 + sobel_y**2)
            edge_strength = np.clip(gradient / 50.0, 0, 1)
            edge_strength_3ch = np.stack([edge_strength] * 3, axis=-1)
            
            result = img.astype(np.float64) + diff_limited * edge_strength_3ch * strength
            
            return np.clip(result, 0, 255).astype(np.uint8)
        except:
            return img
    
    @staticmethod
    def step8_add_grain(img, intensity="medium"):
        """步骤8: 轻微加颗粒"""
        cfg = ProfessionalRestorer.INTENSITY.get(intensity, ProfessionalRestorer.INTENSITY["medium"])
        
        try:
            strength = cfg["grain_strength"]
            
            noise = np.random.normal(0, strength, img.shape).astype(np.float32)
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mask = cv2.threshold(gray, 25, 1, cv2.THRESH_BINARY)[1].astype(np.float32)
            mask = cv2.GaussianBlur(mask, (0, 0), 5)
            mask_3ch = np.stack([mask] * 3, axis=-1)
            
            result = img.astype(np.float32) + noise * mask_3ch
            
            return np.clip(result, 0, 255).astype(np.uint8)
        except:
            return img
    
    @classmethod
    def temporal_stabilize(cls, current_frame, weight=0.2):
        """时序稳定"""
        try:
            cls._frame_buffer.append(current_frame.copy())
            if len(cls._frame_buffer) > cls._max_buffer_size:
                cls._frame_buffer.pop(0)
            
            if len(cls._frame_buffer) < 2:
                return current_frame
            
            result = current_frame.astype(np.float32)
            total_weight = 1.0
            
            for i, frame in enumerate(cls._frame_buffer[:-1]):
                frame_weight = weight * (0.5 ** (len(cls._frame_buffer) - 1 - i))
                diff = np.abs(current_frame.astype(np.float32) - frame.astype(np.float32))
                diff_gray = np.mean(diff, axis=2)
                stable_mask = (diff_gray < 25).astype(np.float32)
                stable_mask = cv2.GaussianBlur(stable_mask, (9, 9), 2.0)
                stable_mask_3ch = np.stack([stable_mask] * 3, axis=-1)
                result = result + frame.astype(np.float32) * frame_weight * stable_mask_3ch
                total_weight = total_weight + frame_weight * stable_mask_3ch
            
            result = result / total_weight
            return np.clip(result, 0, 255).astype(np.uint8)
        except:
            return current_frame
    
    @classmethod
    def clear_frame_buffer(cls):
        cls._frame_buffer = []


# ==================== 10. 并行处理管理器 ====================
class ParallelProcessor:
    """并行处理管理器"""
    
    def __init__(self, max_workers=None, resource_ratio=0.7):
        if max_workers is None:
            cores = os.cpu_count() or 4
            max_workers = max(2, int(cores * resource_ratio))
        self.max_workers = min(max_workers, 8)
        self.resource_ratio = resource_ratio
    
    def process_frame_parallel(self, img, opts, intensity, metrics, original):
        """并行处理单帧的多个后期效果"""
        result = img.copy()
        
        if opts.get("detail_deblock", False):
            result = ProfessionalRestorer.step1_artifact_removal(result, intensity)
        
        if opts.get("detail_presharpen", False):
            result = ProfessionalRestorer.step2_presharpen_with_rollback(result, intensity, metrics)
        
        stage3_results = {}
        
        def do_aa():
            if opts.get("detail_aa", False):
                return ("aa", ProfessionalRestorer.step3_antialiasing(result, intensity))
            return None
        
        def do_denoise():
            if opts.get("detail_denoise", False):
                return ("denoise", ProfessionalRestorer.step4_denoise(result, intensity, metrics))
            return None
        
        with ThreadPoolExecutor(max_workers=min(2, self.max_workers)) as executor:
            futures = [executor.submit(do_aa), executor.submit(do_denoise)]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    stage3_results[res[0]] = res[1]
        
        if "aa" in stage3_results:
            result = stage3_results["aa"]
        if "denoise" in stage3_results:
            aa_result = stage3_results.get("aa", result)
            denoise_result = stage3_results["denoise"]
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY).astype(np.float32)
            edge = cv2.Canny(gray.astype(np.uint8), 50, 150)
            edge_mask = cv2.dilate(edge, np.ones((3,3), np.uint8))
            edge_mask = cv2.GaussianBlur(edge_mask.astype(np.float32), (5,5), 1.0) / 255.0
            edge_mask_3ch = np.stack([edge_mask] * 3, axis=-1)
            result = (aa_result.astype(np.float32) * edge_mask_3ch + 
                     denoise_result.astype(np.float32) * (1 - edge_mask_3ch))
            result = np.clip(result, 0, 255).astype(np.uint8)
        
        if opts.get("detail_face", False):
            result = ProfessionalRestorer.step5_face_repair(result, intensity)
        
        if opts.get("detail_hair", False):
            result = ProfessionalRestorer.step6_hair_protect(result, original, intensity)
        
        if opts.get("detail_final_sharp", False):
            has_other_sharp = opts.get("opt_sharp", False)
            if not has_other_sharp:
                result = ProfessionalRestorer.step7_final_sharpen(result, intensity, metrics)
        
        if opts.get("detail_grain", False):
            result = ProfessionalRestorer.step8_add_grain(result, intensity)
        
        return result


# ==================== 11. 图像处理器 (智能后期) ====================
class ImageProcessor:
    """智能后期处理器"""
    
    INTENSITY = {
        "original": {"bright": 10, "contrast": 1.15, "sat": 1.3, "sharp": 0.5, "grain": 4.5, "denoise": 5},
        "light": {"bright": 5, "contrast": 1.08, "sat": 1.15, "sharp": 0.3, "grain": 2.5, "denoise": 3},
        "medium": {"bright": 10, "contrast": 1.15, "sat": 1.30, "sharp": 0.5, "grain": 4.5, "denoise": 5},
        "heavy": {"bright": 18, "contrast": 1.25, "sat": 1.45, "sharp": 0.7, "grain": 6.5, "denoise": 8},
    }
    
    @staticmethod
    def apply_basic_parallel(img, opts, intensity="medium", metrics=None, smart_mode=False):
        """并行应用基础后期处理"""
        cfg = ImageProcessor.INTENSITY.get(intensity, ImageProcessor.INTENSITY["medium"])
        result = img.copy()
        
        tasks = []
        
        if opts.get('opt_bright'):
            if not smart_mode or not metrics or metrics.get("brightness", 128) < 160:
                tasks.append(("bright", cfg["bright"]))
        
        if opts.get('opt_contrast'):
            if not smart_mode or not metrics or metrics.get("contrast", 50) < 70:
                tasks.append(("contrast", cfg["contrast"]))
        
        if opts.get('opt_sat'):
            if not smart_mode or not metrics or metrics.get("saturation", 100) < 150:
                tasks.append(("sat", cfg["sat"]))
        
        if opts.get('opt_temp'):
            tasks.append(("temp", None))
        
        if opts.get('opt_highlight'):
            tasks.append(("highlight", None))
        
        for task, param in tasks:
            if task == "bright":
                result = cv2.convertScaleAbs(result, alpha=1.0, beta=param)
            elif task == "contrast":
                result = cv2.convertScaleAbs(result, alpha=param, beta=-5)
            elif task == "sat":
                hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype("float32")
                hsv[:,:,1] = np.clip(hsv[:,:,1] * param, 0, 255)
                result = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)
            elif task == "temp":
                b, g, r = cv2.split(result)
                b = cv2.add(b, 8)
                r = cv2.subtract(r, 5)
                result = cv2.merge((b, g, r))
            elif task == "highlight":
                lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
                l, a, b_ch = cv2.split(lab)
                l = cv2.add(l, 10)
                result = cv2.cvtColor(cv2.merge((l, a, b_ch)), cv2.COLOR_LAB2BGR)
        
        return result
    
    @staticmethod
    def apply_advanced_parallel(img, opts, intensity="medium", metrics=None, smart_mode=False):
        """并行应用高级后期处理"""
        cfg = ImageProcessor.INTENSITY.get(intensity, ImageProcessor.INTENSITY["medium"])
        result = img.copy()
        
        def should_apply(key):
            if not opts.get(key):
                return False
            if smart_mode and metrics:
                recommendations = ImageAnalyzer.get_recommendations(metrics)
                rec = recommendations.get(key, {})
                if rec.get("skip"):
                    return False
            return True
        
        if should_apply('opt_auto_wb'):
            lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB).astype(np.float32)
            avg_a, avg_b = np.average(lab[:,:,1]), np.average(lab[:,:,2])
            lab[:,:,1] = lab[:,:,1] - ((avg_a - 128) * (lab[:,:,0] / 255.0) * 1.1)
            lab[:,:,2] = lab[:,:,2] - ((avg_b - 128) * (lab[:,:,0] / 255.0) * 1.1)
            result = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
        
        if should_apply('opt_auto_levels'):
            for i in range(3):
                ch = result[:,:,i]
                lo, hi = np.percentile(ch, [1, 99])
                if hi > lo:
                    result[:,:,i] = np.clip((ch - lo) * 255.0 / (hi - lo), 0, 255).astype(np.uint8)
        
        if should_apply('opt_shadow'):
            hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
            v = hsv[:,:,2]
            mask = np.power(1 - v/255.0, 2)
            hsv[:,:,2] = np.clip(v + 25 * mask, 0, 255)
            result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        if should_apply('opt_highlight_rec'):
            hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype(np.float32)
            v = hsv[:,:,2]
            mask = np.power(v/255.0, 3)
            hsv[:,:,2] = np.clip(v - 20 * mask, 0, 255)
            result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        if should_apply('opt_denoise'):
            denoise_val = cfg.get("denoise", 5)
            result = cv2.fastNlMeansDenoisingColored(result, None, denoise_val, denoise_val, 7, 21)
        
        if should_apply('opt_dehaze'):
            result = ImageProcessor._dehaze(result)
        
        return result
    
    @staticmethod
    def _dehaze(img, strength=0.85):
        img_f = img.astype(np.float64) / 255.0
        dark = np.min(img_f, axis=2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        dark = cv2.erode(dark, kernel)
        h, w = img.shape[:2]
        flat = dark.flatten()
        n = max(1, int(h*w*0.001))
        idx = np.argsort(flat)[-n:]
        A = np.mean(img_f.reshape(-1, 3)[idx], axis=0)
        A = np.clip(A, 0.1, 1.0)
        trans = 1 - strength * cv2.erode(np.min(img_f / np.maximum(A, 0.01), axis=2), kernel)
        trans = np.clip(trans, 0.1, 1.0)
        result = np.zeros_like(img_f)
        for i in range(3):
            result[:,:,i] = (img_f[:,:,i] - A[i]) / np.maximum(trans, 0.1) + A[i]
        return np.clip(result * 255, 0, 255).astype(np.uint8)
    
    @staticmethod
    def apply_filters(img, opts, intensity="medium"):
        """应用滤镜效果"""
        cfg = ImageProcessor.INTENSITY.get(intensity, ImageProcessor.INTENSITY["medium"])
        result = img.copy()
        
        if opts.get('opt_sharp'):
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            mask = cv2.threshold(gray, 25, 1, cv2.THRESH_BINARY)[1].astype(np.float32)
            mask = cv2.GaussianBlur(mask, (0,0), 5)
            mask3 = cv2.merge([mask, mask, mask])
            
            blur = cv2.GaussianBlur(result, (0,0), 2.0)
            unsharp = cv2.addWeighted(result, 1 + cfg["sharp"], blur, -cfg["sharp"], 0)
            result = np.clip(result * (1 - mask3) + unsharp * mask3, 0, 255).astype(np.uint8)
        
        if opts.get('opt_landscape'):
            result = cv2.convertScaleAbs(result, alpha=1.1, beta=0)
            hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV).astype("float32")
            hsv[:,:,1] = np.clip(hsv[:,:,1] * 1.2, 0, 255)
            result = cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2BGR)
            b, g, r = cv2.split(result)
            b = cv2.add(b, 12)
            result = cv2.merge((b, g, r))
        
        if opts.get('opt_vintage'):
            img_f = result.astype(np.float32) / 255.0
            b, g, r = cv2.split(img_f)
            b = b + (1.0 - b) * 0.2 * (1.0 - r)
            r = r + r * 0.2
            result = (np.clip(cv2.merge((b, g, r)), 0, 1) * 255).astype(np.uint8)
        
        if opts.get('opt_cinematic'):
            b, g, r = cv2.split(result.astype(np.float32))
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            b = b + (1 - gray) * 15 * 0.25
            r = r + gray * 10 * 0.25
            result = np.clip(cv2.merge((b, g, r)), 0, 255).astype(np.uint8)
        
        if opts.get('opt_anime_enhance'):
            smoothed = cv2.bilateralFilter(result, 9, 75, 75)
            hsv = cv2.cvtColor(smoothed, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:,:,1] = np.clip(hsv[:,:,1] * 1.2, 0, 255)
            result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        
        if opts.get('opt_grain'):
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            mask = cv2.threshold(gray, 25, 1, cv2.THRESH_BINARY)[1].astype(np.float32)
            mask = cv2.GaussianBlur(mask, (0,0), 5)
            mask3 = cv2.merge([mask, mask, mask])
            noise = np.random.normal(0, cfg["grain"], result.shape).astype(np.float32)
            result = np.clip(result.astype(np.float32) + noise * mask3, 0, 255).astype(np.uint8)
        
        return result


# ==================== 12. 音频处理 ====================
class AudioHandler:
    @staticmethod
    def _get_ffmpeg():
        exe = PM.get_exe("ffmpeg")
        return exe if exe and os.path.isfile(exe) else "ffmpeg"
    
    @staticmethod
    def extract(video, audio):
        try:
            ffmpeg = AudioHandler._get_ffmpeg()
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run([ffmpeg, '-i', video, '-vn', '-acodec', 'copy', '-y', audio],
                         capture_output=True, startupinfo=si, timeout=60)
            return os.path.exists(audio) and os.path.getsize(audio) > 0
        except:
            return False
    
    # ==================== 4. 替换 AudioHandler 类的 merge_h264 方法 ====================
    @staticmethod
    def merge_h264(video_frames_dir, audio, output, fps, width, height):
        """使用FFmpeg的H.264编码合并视频 - 2025万能兼容版"""
        try:
            ffmpeg = AudioHandler._get_ffmpeg()
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            if not os.path.isfile(ffmpeg):
                print(f"[FFmpeg错误] FFmpeg不存在: {ffmpeg}")
                return False
            
            first_frame = os.path.join(video_frames_dir, 'frame_000000.png')
            if not os.path.exists(first_frame):
                print(f"[FFmpeg错误] 帧文件不存在: {first_frame}")
                return False
            
            # GOP大小：30fps用90，60fps用180
            gop_size = 90 if fps <= 30 else 180
            keyint_min = 30 if fps <= 30 else 60
            
            cmd = [
                ffmpeg,
                '-y',
                '-framerate', str(fps),
                '-i', os.path.join(video_frames_dir, 'frame_%06d.png'),
            ]
            
            if audio and os.path.exists(audio):
                cmd.extend(['-i', audio])
            
            # 2025万能兼容参数
            cmd.extend([
                '-c:v', 'libx264',
                '-profile:v', 'main',
                '-level', '4.0',
                '-preset', 'medium',
                '-crf', '23',                    # 画质优秀，体积更小
                '-pix_fmt', 'yuv420p',
                '-g', str(gop_size),             # 关键帧间隔
                '-keyint_min', str(keyint_min),
                '-bf', '2',
                '-movflags', '+faststart',       # 网页秒开必加
            ])
            
            if audio and os.path.exists(audio):
                cmd.extend([
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-ac', '2',
                ])
            
            cmd.append(output)
            
            print(f"[FFmpeg] 万能兼容编码中...")
            
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                startupinfo=si, 
                timeout=600,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0:
                print(f"[FFmpeg错误] 返回码: {result.returncode}")
                print(f"[FFmpeg stderr] {result.stderr[:500] if result.stderr else '无'}")
                return False
            
            if os.path.exists(output) and os.path.getsize(output) > 1000:
                print(f"[FFmpeg] 编码成功: {output}")
                return True
            else:
                print(f"[FFmpeg错误] 输出文件无效")
                return False
                
        except subprocess.TimeoutExpired:
            print("[FFmpeg错误] 编码超时")
            return False
        except Exception as e:
            print(f"[FFmpeg错误] 异常: {e}")
            return False
    
    @staticmethod
    def merge(video, audio, output):
        """合并视频和音频"""
        try:
            ffmpeg = AudioHandler._get_ffmpeg()
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run([ffmpeg, '-i', video, '-i', audio, '-c:v', 'copy',
                          '-c:a', 'aac', '-strict', 'experimental', '-y', output],
                         capture_output=True, startupinfo=si, timeout=120)
            return os.path.exists(output)
        except:
            return False
    
    # ==================== 5. 替换 AudioHandler 类的 encode_h264 方法 ====================
    @staticmethod
    def encode_h264(input_raw, output, fps):
        """将原始视频重新编码为H.264 - 2025万能兼容版"""
        try:
            ffmpeg = AudioHandler._get_ffmpeg()
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            gop_size = 90 if fps <= 30 else 180
            keyint_min = 30 if fps <= 30 else 60
            
            cmd = [
                ffmpeg,
                '-y',
                '-i', input_raw,
                '-c:v', 'libx264',
                '-profile:v', 'main',
                '-level', '4.0',
                '-preset', 'medium',
                '-crf', '23',
                '-pix_fmt', 'yuv420p',
                '-g', str(gop_size),
                '-keyint_min', str(keyint_min),
                '-bf', '2',
                '-movflags', '+faststart',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-ac', '2',
                output
            ]
            
            subprocess.run(cmd, capture_output=True, startupinfo=si, timeout=600)
            return os.path.exists(output)
        except:
            return False

# ==================== 13. 视频处理管线 ====================
STOP_FLAG = False
PAUSE_FLAG = False

class VideoPipeline:
    """视频处理管线 - H.264编码优化版"""
    
    def __init__(self, task, log_func, gpu_info, resource_ratio=0.7):
        self.task = task
        self.log = log_func
        self.resource_ratio = resource_ratio
        self.sample_metrics = None
        self.smart_mode = task.smart_mode
        
        cores = gpu_info.get("cores", 4)
        self.max_workers = max(2, min(8, int(cores * resource_ratio)))
        self.parallel_processor = ParallelProcessor(self.max_workers, resource_ratio)
    
    def run(self, progress_cb, time_cb=None, status_cb=None):
        global STOP_FLAG, PAUSE_FLAG
        start_time = time.time()
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, "audio.aac")
        frames_dir = os.path.join(temp_dir, "frames")
        temp_video = os.path.join(temp_dir, "temp_raw.mp4")
        os.makedirs(frames_dir, exist_ok=True)
        
        try:
            has_audio = AudioHandler.extract(self.task.input_path, audio_path)
            self.log(f"音频: {'有' if has_audio else '无'}")
            
            cap = cv2.VideoCapture(self.task.input_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.task.total_frames = total
            self.log(f"视频: {w}x{h}, {fps:.1f}fps, {total}帧")
            self.log(f"并行线程: {self.max_workers}")
            
            cfg = self.task.get_config()
            
            if self.smart_mode or cfg.get("use_detail_restore"):
                self.log("🔍 智能分析中...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
                ret, sample_frame = cap.read()
                if ret:
                    self.sample_metrics = ImageAnalyzer.analyze(sample_frame)
                    self.log(f"📊 亮度:{self.sample_metrics['brightness']:.0f} "
                            f"对比:{self.sample_metrics['contrast']:.0f} "
                            f"清晰:{self.sample_metrics['sharpness']:.0f}")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            ProfessionalRestorer.clear_frame_buffer()
            
            processed = self._process_frames_to_sequence(
                cap, frames_dir, total, fps, progress_cb, time_cb, start_time, cfg
            )
            
            cap.release()
            
            if STOP_FLAG:
                self.log("⏹ 处理已停止")
                return processed, time.time() - start_time
            
            self.log("📦 正在编码 H.264...")
            if status_cb:
                status_cb("正在编码视频...")
            
            if AudioHandler.merge_h264(frames_dir, audio_path if has_audio else None, 
                                       self.task.output_path, fps, w, h):
                self.log("✅ H.264编码完成")
            else:
                self.log("⚠️ FFmpeg编码失败，尝试备用方案...")
                writer = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, (w, h))
                
                frame_files = sorted(glob.glob(os.path.join(frames_dir, 'frame_*.png')))
                for frame_file in frame_files:
                    frame = cv2.imread(frame_file)
                    if frame is not None:
                        writer.write(frame)
                writer.release()
                
                if has_audio:
                    AudioHandler.merge(temp_video, audio_path, self.task.output_path)
                else:
                    AudioHandler.encode_h264(temp_video, self.task.output_path, fps)
            
            elapsed = time.time() - start_time
            return processed, elapsed
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _process_frames_to_sequence(self, cap, frames_dir, total, fps, progress_cb, time_cb, start_time, cfg):
        global STOP_FLAG, PAUSE_FLAG
        
        processed = 0
        frame_times = []
        
        basic_int = cfg.get("basic_intensity", "medium")
        adv_int = cfg.get("adv_intensity", "medium")
        detail_int = cfg.get("detail_intensity", "medium")
        
        while not STOP_FLAG:
            while PAUSE_FLAG and not STOP_FLAG:
                time.sleep(0.1)
            
            if STOP_FLAG:
                break
            
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_start = time.time()
            
            result = self._process_frame(frame, cfg, basic_int, adv_int, detail_int)
            
            frame_path = os.path.join(frames_dir, f'frame_{processed:06d}.png')
            cv2.imwrite(frame_path, result)
            
            processed += 1
            self.task.current_frame = processed
            self.task.progress = processed / total * 100
            
            frame_time = time.time() - frame_start
            frame_times.append(frame_time)
            if len(frame_times) > 30:
                frame_times.pop(0)
            
            current_fps = 1.0 / (sum(frame_times) / len(frame_times)) if frame_times else 0
            self.task.fps = current_fps
            
            elapsed = time.time() - start_time
            self.task.elapsed_time = elapsed
            
            if progress_cb:
                progress_cb(processed, total, current_fps)
            if time_cb:
                time_cb(elapsed)
        
        return processed
    
    def _process_frame(self, frame, cfg, basic_int, adv_int, detail_int):
        result = frame.copy()
        original = frame.copy()
        
        result = ProfessionalRestorer.temporal_stabilize(result)
        
        if cfg.get("use_detail_restore"):
            result = self.parallel_processor.process_frame_parallel(
                result, cfg, detail_int, self.sample_metrics, original
            )
        
        if cfg.get("use_basic"):
            result = ImageProcessor.apply_basic_parallel(
                result, cfg, basic_int, self.sample_metrics, self.smart_mode
            )
        
        if cfg.get("use_advanced"):
            result = ImageProcessor.apply_advanced_parallel(
                result, cfg, adv_int, self.sample_metrics, self.smart_mode
            )
        
        result = ImageProcessor.apply_filters(result, cfg, basic_int)
        
        return result


# ==================== 14. 预览窗口 ====================
class PreviewWindow:
    def __init__(self, master, orig, proc):
        self.top = Toplevel(master)
        self.top.title("效果对比 - 拖动分割线")
        self.top.geometry("960x660")
        self.top.configure(bg="#2D3142")
        self.w, self.h = 920, 580
        self.orig = cv2.resize(orig, (self.w, self.h))
        self.proc = cv2.resize(proc, (self.w, self.h))
        self.split = self.w // 2
        Label(self.top, text="← 原始 | 处理后 →", font=("微软雅黑", 11), bg="#2D3142", fg="#E8E8E8").pack(pady=5)
        self.cv = Canvas(self.top, width=self.w, height=self.h, bg="black", cursor="sb_h_double_arrow")
        self.cv.pack(pady=5)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonPress-1>", self._drag)
        self._update()
    
    def _drag(self, e):
        self.split = max(0, min(e.x, self.w))
        self._update()
    
    def _update(self):
        img = self.proc.copy()
        img[:, :self.split] = self.orig[:, :self.split]
        cv2.line(img, (self.split, 0), (self.split, self.h), (0, 255, 255), 2)
        cv2.putText(img, "Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        cv2.putText(img, "Enhanced", (self.w-120, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
        self.cv.create_image(0, 0, anchor="nw", image=self.tk_img)

# ==================== 15. 新建任务对话框 ====================
class NewTaskDialog:
    """新建/编辑任务对话框 - 深色主题版"""
    
    # 深色主题配色
    DARK_BG = "#2D2D2D"           # 主背景色
    DARK_FRAME_BG = "#3D3D3D"     # 框架背景色
    DARK_TEXT = "#E0E0E0"         # 主文字颜色
    DARK_SUBTEXT = "#A0A0A0"      # 次要文字颜色
    DARK_BORDER = "#505050"       # 边框颜色
    
    COLORS = {
        "detail_deblock": "#FF8C00",
        "detail_presharpen": "#FFD700",
        "detail_aa": "#20B2AA",
        "detail_denoise": "#778899",
        "detail_face": "#FF69B4",
        "detail_hair": "#DDA0DD",
        "detail_final_sharp": "#98FB98",
        "detail_grain": "#A9A9A9",
        "opt_bright": "#FFB347",
        "opt_contrast": "#FF8C69",
        "opt_sat": "#FF69B4",
        "opt_temp": "#87CEEB",
        "opt_highlight": "#DDA0DD",
        "opt_sharp": "#90EE90",
        "opt_grain": "#98FB98",
        "opt_landscape": "#40E0D0",
        "opt_vintage": "#D2B48C",
        "opt_cinematic": "#BA55D3",
        "opt_anime_enhance": "#FF69B4",
        "opt_auto_wb": "#40E0D0",
        "opt_auto_levels": "#20B2AA",
        "opt_denoise": "#778899",
        "opt_shadow": "#708090",
        "opt_highlight_rec": "#FFD700",
        "opt_dehaze": "#A9A9A9",
    }
    
    def __init__(self, master, input_path, existing_task=None):
        self.master = master
        self.input_path = input_path
        self.existing_task = existing_task
        self.result = None
        
        self.dialog = Toplevel(master)
        self.dialog.title("新建任务" if not existing_task else "编辑任务")
        self.dialog.geometry("550x650")
        self.dialog.configure(bg=self.DARK_BG)  # 深色背景
        self.dialog.resizable(False, False)  # 禁止调整窗口大小
        self.dialog.transient(master)
        self.dialog.grab_set()
        
        self._init_vars()
        self._init_ui()
        
        if existing_task:
            self._load_from_task(existing_task)
        
        self.dialog.wait_window()
    
    def _init_vars(self):
        self.use_detail = BooleanVar(value=False)
        self.detail_intensity = StringVar(value="medium")
        self.detail_opts = {
            "detail_deblock": BooleanVar(value=True),
            "detail_presharpen": BooleanVar(value=True),
            "detail_aa": BooleanVar(value=True),
            "detail_denoise": BooleanVar(value=True),
            "detail_face": BooleanVar(value=True),
            "detail_hair": BooleanVar(value=True),
            "detail_final_sharp": BooleanVar(value=True),
            "detail_grain": BooleanVar(value=False),
        }
        
        self.use_basic = BooleanVar(value=False)
        self.basic_intensity = StringVar(value="medium")
        self.basic_opts = {
            'opt_bright': BooleanVar(value=True),
            'opt_contrast': BooleanVar(value=True),
            'opt_sat': BooleanVar(value=True),
            'opt_temp': BooleanVar(value=True),
            'opt_highlight': BooleanVar(value=True),
            'opt_sharp': BooleanVar(value=True),
            'opt_grain': BooleanVar(value=True),
        }
        self.filter_opts = {
            'opt_landscape': BooleanVar(),
            'opt_vintage': BooleanVar(),
            'opt_cinematic': BooleanVar(),
            'opt_anime_enhance': BooleanVar(),
        }
        
        self.use_advanced = BooleanVar(value=False)
        self.adv_intensity = StringVar(value="medium")
        self.smart_mode = BooleanVar(value=True)
        self.adv_opts = {
            'opt_auto_wb': BooleanVar(value=True),
            'opt_auto_levels': BooleanVar(value=True),
            'opt_denoise': BooleanVar(value=True),
            'opt_shadow': BooleanVar(value=True),
            'opt_highlight_rec': BooleanVar(value=True),
            'opt_dehaze': BooleanVar(value=False),  # 去雾默认不选，与全选一致
        }
    
    def _create_colored_check(self, parent, text, var, color):
        """创建彩色复选框 - 深色主题"""
        cb = Checkbutton(parent, text=text, variable=var,
                        fg=color, bg=self.DARK_FRAME_BG, 
                        activebackground=self.DARK_FRAME_BG,
                        selectcolor=self.DARK_BG, font=("微软雅黑", 9))
        return cb
    
    def _create_section(self, parent, title, use_var, intensity_var, opts_dict, 
                       items_config, title_color="#333", on_toggle=None,
                       select_all_exclude=None):
        """创建配置区块 - 深色主题，带全选按钮
        
        Args:
            select_all_exclude: 全选时排除的选项key列表，如 ["detail_grain"]
        """
        frame = LabelFrame(parent, text=title, bg=self.DARK_FRAME_BG, fg=title_color,
                          font=("微软雅黑", 10, "bold"), padx=10, pady=5)
        frame.pack(fill='x', padx=10, pady=5)
        
        # 顶部行：启用复选框 + 强度选择 + 全选按钮
        top_row = Frame(frame, bg=self.DARK_FRAME_BG)
        top_row.pack(fill='x', pady=2)
        
        # 左侧：启用复选框
        Checkbutton(top_row, text="启用", variable=use_var, bg=self.DARK_FRAME_BG,
                   fg=title_color, font=("微软雅黑", 9, "bold"),
                   selectcolor=self.DARK_BG, activebackground=self.DARK_FRAME_BG,
                   command=on_toggle).pack(side='left')
        
        # 强度选择
        Label(top_row, text="强度:", bg=self.DARK_FRAME_BG, fg=self.DARK_SUBTEXT,
              font=("微软雅黑", 9)).pack(side='left', padx=(15, 5))
        
        from tkinter import Radiobutton
        for text, val in [("轻度", "light"), ("中度", "medium"), ("重度", "heavy")]:
            Radiobutton(top_row, text=text, variable=intensity_var, value=val,
                       bg=self.DARK_FRAME_BG, fg=self.DARK_TEXT, 
                       selectcolor=self.DARK_BG, activebackground=self.DARK_FRAME_BG,
                       font=("微软雅黑", 9)).pack(side='left', padx=2)
        
        # 右侧：全选和取消全选按钮
        def select_all():
            for key, var in opts_dict.items():
                if select_all_exclude and key in select_all_exclude:
                    continue  # 跳过排除的选项
                var.set(True)
        
        def deselect_all():
            for key, var in opts_dict.items():
                var.set(False)
        
        Button(top_row, text="取消全选", command=deselect_all, 
               bg="#666666", fg="white", font=("微软雅黑", 8),
               relief="flat", padx=8, pady=1).pack(side='right', padx=2)
        
        Button(top_row, text="全选", command=select_all, 
               bg="#4CAF50", fg="white", font=("微软雅黑", 8),
               relief="flat", padx=8, pady=1).pack(side='right', padx=2)
        
        # 选项网格
        opts_frame = Frame(frame, bg=self.DARK_FRAME_BG)
        opts_frame.pack(fill='x', pady=5)
        
        row = 0
        col = 0
        max_cols = 4
        
        for text, key, color in items_config:
            if key in opts_dict:
                cb = self._create_colored_check(opts_frame, text, opts_dict[key], color)
                cb.grid(row=row, column=col, sticky='w', padx=2, pady=1)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
        
        return frame
    
    def _init_ui(self):
        """初始化UI - 深色主题"""
        # 文件信息区域 - 深灰色
        file_frame = Frame(self.dialog, bg="#505050", relief="flat")
        file_frame.pack(fill='x', padx=10, pady=10)
        Label(file_frame, text=f"📁 {os.path.basename(self.input_path)}", 
              bg="#505050", fg=self.DARK_TEXT, font=("微软雅黑", 10)).pack(pady=8, padx=10)
        
        # 滚动区域 - 不显示滚动条
        canvas = Canvas(self.dialog, bg=self.DARK_BG, highlightthickness=0)
        scroll_frame = Frame(canvas, bg=self.DARK_BG)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=540)
        
        # 绑定鼠标滚轮事件
        # 绑定鼠标滚轮事件 - 仅在canvas区域内有效
        def on_mousewheel(event):
            try:
                # 检查canvas是否存在且有效
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except:
                pass

        # 使用局部绑定而非全局绑定
        canvas.bind("<MouseWheel>", on_mousewheel)
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 对话框关闭时解除绑定
        def on_dialog_close():
            try:
                canvas.unbind_all("<MouseWheel>")
            except:
                pass
            self.dialog.destroy()

        self.dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=5)
        
        # ===== 细节修复区块 =====
        detail_items = [
            ("🧱伪影移除", "detail_deblock", self.COLORS["detail_deblock"]),
            ("⚡预锐化", "detail_presharpen", self.COLORS["detail_presharpen"]),
            ("🔍抗锯齿", "detail_aa", self.COLORS["detail_aa"]),
            ("🔇去噪", "detail_denoise", self.COLORS["detail_denoise"]),
            ("👤人脸", "detail_face", self.COLORS["detail_face"]),
            ("💇毛发", "detail_hair", self.COLORS["detail_hair"]),
            ("✨锐化", "detail_final_sharp", self.COLORS["detail_final_sharp"]),
            ("📷颗粒", "detail_grain", self.COLORS["detail_grain"]),
        ]
        # 全选排除"颗粒"
        self._create_section(scroll_frame, "🔧 细节修复", self.use_detail, 
                            self.detail_intensity, self.detail_opts, detail_items, 
                            "#FF8C00", select_all_exclude=["detail_grain"])
        
        # ===== 智能后期区块 =====
        basic_items = [
            ("✨提亮", "opt_bright", self.COLORS["opt_bright"]),
            ("📊对比", "opt_contrast", self.COLORS["opt_contrast"]),
            ("🌈鲜艳", "opt_sat", self.COLORS["opt_sat"]),
            ("❄️冷白", "opt_temp", self.COLORS["opt_temp"]),
            ("🔅压光", "opt_highlight", self.COLORS["opt_highlight"]),
            ("🔪锐化", "opt_sharp", self.COLORS["opt_sharp"]),
            ("📷质感", "opt_grain", self.COLORS["opt_grain"]),
        ]
        # 智能后期全选包括全部
        self._create_section(scroll_frame, "🎨 智能后期", self.use_basic,
                            self.basic_intensity, self.basic_opts, basic_items, 
                            "#FFB347", select_all_exclude=None)
        
        # ===== 滤镜效果区块 =====
        filter_frame = LabelFrame(scroll_frame, text="🎭 滤镜效果", 
                                 bg=self.DARK_FRAME_BG, fg="#BA55D3",
                                 font=("微软雅黑", 10, "bold"), padx=10, pady=5)
        filter_frame.pack(fill='x', padx=10, pady=5)
        
        filter_row = Frame(filter_frame, bg=self.DARK_FRAME_BG)
        filter_row.pack(fill='x')
        
        filter_items = [
            ("🌄风景", "opt_landscape", self.COLORS["opt_landscape"]),
            ("🎞️老电影", "opt_vintage", self.COLORS["opt_vintage"]),
            ("🎬电影", "opt_cinematic", self.COLORS["opt_cinematic"]),
            ("🎌动漫", "opt_anime_enhance", self.COLORS["opt_anime_enhance"]),
        ]
        for text, key, color in filter_items:
            self._create_colored_check(filter_row, text, self.filter_opts[key], color).pack(side='left', padx=5)
        
        # ===== 高级后期区块 =====
        adv_items = [
            ("🎨白平衡", "opt_auto_wb", self.COLORS["opt_auto_wb"]),
            ("📈色阶", "opt_auto_levels", self.COLORS["opt_auto_levels"]),
            ("🔇降噪", "opt_denoise", self.COLORS["opt_denoise"]),
            ("🌑暗部", "opt_shadow", self.COLORS["opt_shadow"]),
            ("☀️高光", "opt_highlight_rec", self.COLORS["opt_highlight_rec"]),
            ("🌫️去雾", "opt_dehaze", self.COLORS["opt_dehaze"]),
        ]
        # 全选排除"去雾"
        adv_frame = self._create_section(scroll_frame, "🔬 高级后期", self.use_advanced,
                                         self.adv_intensity, self.adv_opts, adv_items, 
                                         "#7B68EE", select_all_exclude=["opt_dehaze"])
        
        # 智能模式复选框
        smart_row = Frame(adv_frame, bg=self.DARK_FRAME_BG)
        smart_row.pack(fill='x', pady=2)
        Checkbutton(smart_row, text="🧠 智能模式 (自动分析画面质量)", variable=self.smart_mode,
                   bg=self.DARK_FRAME_BG, fg="#50C878", font=("微软雅黑", 9), 
                   selectcolor=self.DARK_BG, activebackground=self.DARK_FRAME_BG).pack(anchor='w')
        
        # ===== 按钮区域 - 高级后期区块下方右对齐 =====
        btn_frame = Frame(scroll_frame, bg=self.DARK_BG)
        btn_frame.pack(fill='x', padx=10, pady=(10, 15), anchor='e')
        
        # 取消按钮 - 右侧
        Button(btn_frame, text="取消", command=self._cancel, bg="#9E9E9E", fg="white",
               font=("微软雅黑", 10), width=12, relief="flat").pack(side='right', padx=(5, 0))
        
        # 应用按钮 - 取消按钮左边
        Button(btn_frame, text="应用", command=self._apply, bg="#4CAF50", fg="white",
               font=("微软雅黑", 10), width=12, relief="flat").pack(side='right', padx=5)
    
    def _load_from_task(self, task):
        self.use_detail.set(task.use_detail_restore)
        self.detail_intensity.set(task.detail_intensity)
        for k, v in task.detail_opts.items():
            if k in self.detail_opts:
                self.detail_opts[k].set(v)
        
        self.use_basic.set(task.use_basic)
        self.basic_intensity.set(task.basic_intensity)
        for k, v in task.basic_opts.items():
            if k in self.basic_opts:
                self.basic_opts[k].set(v)
        for k, v in task.filter_opts.items():
            if k in self.filter_opts:
                self.filter_opts[k].set(v)
        
        self.use_advanced.set(task.use_advanced)
        self.adv_intensity.set(task.adv_intensity)
        self.smart_mode.set(task.smart_mode)
        for k, v in task.adv_opts.items():
            if k in self.adv_opts:
                self.adv_opts[k].set(v)
    
    def _apply(self):
        """应用配置 - 修复文件名重复问题"""
        base, ext = os.path.splitext(self.input_path)
        
        # 生成不重复的输出文件名
        output_path = f"{base}_Enhanced.mp4"
        counter = 1
        while os.path.exists(output_path):
            output_path = f"{base}_Enhanced_{counter}.mp4"
            counter += 1
        
        task = TaskItem(
            task_id=str(uuid.uuid4())[:8],
            input_path=self.input_path,
            output_path=output_path,
            use_detail_restore=self.use_detail.get(),
            detail_intensity=self.detail_intensity.get(),
            detail_opts={k: v.get() for k, v in self.detail_opts.items()},
            use_basic=self.use_basic.get(),
            basic_intensity=self.basic_intensity.get(),
            basic_opts={k: v.get() for k, v in self.basic_opts.items()},
            filter_opts={k: v.get() for k, v in self.filter_opts.items()},
            use_advanced=self.use_advanced.get(),
            adv_intensity=self.adv_intensity.get(),
            smart_mode=self.smart_mode.get(),
            adv_opts={k: v.get() for k, v in self.adv_opts.items()},
        )
        
        self.result = task
        # ↓↓↓ 新增的4行代码 ↓↓↓
        # 关闭对话框前，解除全局鼠标滚轮绑定，避免报错
        try:
            self.dialog.unbind_all("<MouseWheel>")
        except:
            pass
        # ↑↑↑ 新增的4行代码 ↑↑↑
        self.dialog.destroy()
    
    def _cancel(self):
        self.result = None
        # ↓↓↓ 新增的4行代码 ↓↓↓
        # 关闭对话框前，解除全局鼠标滚轮绑定，避免报错
        try:
            self.dialog.unbind_all("<MouseWheel>")
        except:
            pass
        # ↑↑↑ 新增的4行代码 ↑↑↑
        self.dialog.destroy()
    
# ==================== 16. 主界面 (仿Video2X风格) - 修复版 ====================
class App:
    """主应用界面 - 仿Video2X风格，修复日志面板和任务列表对齐问题"""
    
    # 统一的列宽定义，确保表头和任务行使用相同的值
    COLUMN_WIDTHS = [0.30, 0.25, 0.25, 0.10, 0.10]
    COLUMN_NAMES = ["文件名", "处理任务", "进度", "编辑", "删除"]

    # 任务状态对应的背景颜色
    STATUS_COLORS = {
        TaskStatus.PENDING: "#FFFFFF",      # 待处理 - 白色
        TaskStatus.RUNNING: "#E3F2FD",      # 运行中 - 浅蓝色
        TaskStatus.PAUSED: "#FFE4E8",       # 暂停 - 粉色
        TaskStatus.STOPPED: "#FFCDD2",      # 停止 - 浅红色
        TaskStatus.COMPLETED: "#E8F5E9",    # 完成 - 浅绿色
        TaskStatus.FAILED: "#FFEBEE",       # 失败 - 浅红色
        "selected": "#FFF8DC",              # 选中 - 黄色
    }
    
    # 进度条颜色
    PROGRESS_COLORS = {
        "running": "#2196F3",    # 运行中 - 蓝色
        "completed": "#4CAF50",  # 完成 - 绿色
        "paused": "#FF9800",     # 暂停 - 橙色
        "stopped": "#F44336",    # 停止 - 红色
    }
    
    def __init__(self):
        try:
            from tkinterdnd2 import DND_FILES, TkinterDnD
            self.root = TkinterDnD.Tk()
            self.dnd_available = True
        except:
            from tkinter import Tk
            self.root = Tk()
            self.dnd_available = False
        
        self.root.title("笔记本高清视频修复 2025 V7.0")
        self.root.geometry("800x650")
        self.root.configure(bg="white")
        
        # ===== 日志面板尺寸常量（必须在 _init_ui 之前定义）=====
        self.log_min_width = 180   # 日志面板最小宽度
        self.log_max_width = 360   # 日志面板最大宽度
        self.main_min_width = 400  # 主窗口（不含日志）最小宽度
        self.min_height = 450      # 窗口最小高度
        
        self.root.minsize(self.main_min_width, self.min_height)
        
        self.activated = False
        self.gpu = GPUDetector()
        self.checker = EnvironmentChecker(self._log)
        self.downloader = RobustDownloader(self._log)
        self.task_manager = TaskManager()
        
        self.is_running = False
        self.is_paused = False
        self.current_processing_task = None
        self.log_visible = False
        self.selected_task_id = None
        self._last_width = 800  # 记录上次窗口宽度
        # 新增：设置变量
        self.setting_on_complete = StringVar(value="nothing")  # 处理完成后的操作
        self.setting_auto_show_stats = BooleanVar(value=False)  # 自动显示统计数据
        self.setting_delete_completed = BooleanVar(value=False)  # 删除已完成任务
        
        self._check_key()
        self._init_ui()
        self._setup_drop()
        
        if not self.activated:
            self._start_trial()
        
        self._update_status("就绪")
    
    def _check_key(self):
        self.mac = LicenseManager.get_machine_code()
        if LicenseManager.check_license_file():
            self.activated = True
        else:
            self._show_activation()
    
    def _show_activation(self):
        """显示激活窗口 - 居中于主窗口"""
        win = Toplevel(self.root)
        win.title("软件激活")
        win.geometry("400x300")
        win.config(bg="white")
        win.transient(self.root)
        win.grab_set()
        
        # 等待主窗口显示完成后再计算居中位置
        self.root.update_idletasks()
        
        # 计算居中位置
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        
        win_w = 400
        win_h = 300
        
        # 计算激活窗口应该出现的位置（主窗口中心）
        x = main_x + (main_w - win_w) // 2
        y = main_y + (main_h - win_h) // 2
        
        # 确保窗口不会超出屏幕
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = max(0, min(x, screen_w - win_w))
        y = max(0, min(y, screen_h - win_h))
        
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        Label(win, text="📋 机器码:", bg="white", fg="#333", font=("微软雅黑", 11)).pack(pady=15)
        e1 = Entry(win, width=35, font=("Consolas", 12), justify="center", relief="solid", bd=1)
        e1.pack(ipady=5)
        e1.insert(0, self.mac)
        
        Label(win, text="🔑 激活密钥:", bg="white", fg="#333", font=("微软雅黑", 11)).pack(pady=15)
        e2 = Entry(win, width=35, font=("Consolas", 12), justify="center", relief="solid", bd=1)
        e2.pack(ipady=5)
        
        def activate():
            if LicenseManager.verify_key(self.mac, e2.get()):
                LicenseManager.save_license()
                self.activated = True
                messagebox.showinfo("成功", "✅ 激活成功!")
                win.destroy()
            else:
                messagebox.showerror("错误", "❌ 密钥无效")
        
        btn_frame = Frame(win, bg="white")
        btn_frame.pack(pady=20)
        
        Button(btn_frame, text="✅ 激活", command=activate, bg="#4CAF50", fg="white",
            width=15, font=("微软雅黑", 10), relief="flat").pack(side=LEFT, padx=10)
        Button(btn_frame, text="⏰ 试用15分钟", command=win.destroy, bg="#9E9E9E", fg="white",
            width=15, font=("微软雅黑", 10), relief="flat").pack(side=LEFT, padx=10)
        
        Label(win, text="客服: u788990@163.com", bg="white", fg="#999").pack(pady=20)
        self.root.wait_window(win)
    
    def _start_trial(self):
        """试用模式 - 15分钟后强制停止任务并退出"""
        self.trial_mins = 15
        self.trial_expired = False  # 新增：试用过期标志
        
        def tick():
            # 如果已激活，停止试用倒计时
            if self.activated:
                return
            
            # 如果已过期，不再处理（防止重复触发）
            if self.trial_expired:
                return
            
            self.trial_mins -= 1
            
            if self.trial_mins <= 0:
                # 标记试用已过期
                self.trial_expired = True
                
                # 停止所有正在运行的任务
                global STOP_FLAG
                STOP_FLAG = True
                
                self._log("[warning] 试用时间到，正在停止任务...")
                
                # 禁用所有控件，防止继续操作
                self._disable_all_controls()
                
                # 延迟显示退出窗口，给任务一点时间停止
                self.root.after(500, self._show_trial_expired_dialog)
            else:
                # 更新标题显示剩余时间
                self.root.title(f"笔记本高清视频修复 V7.0 (试用:{self.trial_mins}分)")
                # 安排下一次tick
                self.root.after(60000, tick)
        
        # 60秒后第一次tick
        self.root.after(60000, tick)

    def _show_trial_expired_dialog(self):
        """显示试用过期对话框 - 60秒后强制退出，不可取消"""
        
        # 创建模态对话框
        exit_win = Toplevel(self.root)
        exit_win.title("试用结束")
        exit_win.geometry("400x220")
        exit_win.configure(bg="white")
        exit_win.transient(self.root)
        exit_win.grab_set()
        
        # 禁止通过X按钮关闭
        exit_win.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # 禁止通过Alt+F4关闭（Windows）
        exit_win.bind('<Alt-F4>', lambda e: 'break')
        
        # 置顶显示
        try:
            exit_win.attributes('-topmost', True)
        except:
            pass
        
        # 居中显示
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        win_w, win_h = 400, 220
        x = main_x + (main_w - win_w) // 2
        y = main_y + (main_h - win_h) // 2
        x = max(0, min(x, self.root.winfo_screenwidth() - win_w))
        y = max(0, min(y, self.root.winfo_screenheight() - win_h))
        exit_win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # UI元素
        Label(exit_win, text="⏰", font=("", 40), bg="white", fg="#FF9800").pack(pady=10)
        
        countdown_seconds = 60
        countdown_var = [countdown_seconds]  # 使用列表以便在闭包中修改
        
        msg_label = Label(exit_win, 
                        text=f"试用时间已到，程序将在 {countdown_var[0]} 秒后自动退出。\n请联系客服获取激活密钥：u788990@163.com",
                        bg="white", fg="#333", font=("微软雅黑", 10), justify="center")
        msg_label.pack(pady=10)
        
        btn = Button(exit_win, text=f"立即退出 ({countdown_var[0]}s)", 
                    command=lambda: self._do_force_exit(), 
                    bg="#F44336", fg="white",
                    font=("微软雅黑", 10, "bold"), width=18, relief="flat")
        btn.pack(pady=10)
        
        # 保存引用，供 _do_force_exit 使用
        self._trial_exit_win = exit_win
        
        def update_countdown():
            # 检查窗口是否仍然存在
            try:
                if not exit_win.winfo_exists():
                    # 窗口被意外关闭，立即强制退出
                    self._do_force_exit()
                    return
            except:
                # 任何异常都强制退出
                self._do_force_exit()
                return
            
            countdown_var[0] -= 1
            
            if countdown_var[0] <= 0:
                # 倒计时结束，强制退出
                self._do_force_exit()
            else:
                try:
                    msg_label.config(text=f"试用时间已到，程序将在 {countdown_var[0]} 秒后自动退出。\n请联系客服获取激活密钥：u788990@163.com")
                    btn.config(text=f"立即退出 ({countdown_var[0]}s)")
                    exit_win.after(1000, update_countdown)
                except:
                    # 更新UI失败，强制退出
                    self._do_force_exit()
        
        # 开始倒计时
        exit_win.after(1000, update_countdown)
    
    def _disable_all_controls(self):
        """禁用所有控件，防止用户在退出倒计时期间继续操作"""
        try:
            # 禁用主要操作按钮
            if hasattr(self, 'btn_start'):
                self.btn_start.config(state=DISABLED)
            if hasattr(self, 'btn_pause'):
                self.btn_pause.config(state=DISABLED)
            if hasattr(self, 'btn_stop'):
                self.btn_stop.config(state=DISABLED)
            if hasattr(self, 'btn_stats'):
                self.btn_stats.config(state=DISABLED)
            if hasattr(self, 'btn_log'):
                self.btn_log.config(state=DISABLED)
            
            # 更新状态栏提示
            self._update_status("试用时间已到，程序即将退出...")
            
            # 更新标题
            self.root.title("笔记本高清视频修复 V7.0 - 试用已过期")
        except:
            pass
    def _do_force_exit(self):
        """执行强制退出 - 确保程序一定能退出"""
        
        # 第一步：尝试关闭退出对话框
        try:
            if hasattr(self, '_trial_exit_win') and self._trial_exit_win.winfo_exists():
                self._trial_exit_win.destroy()
        except:
            pass
        
        # 第二步：尝试正常关闭主窗口
        try:
            self.root.quit()  # 退出 mainloop
        except:
            pass
        
        try:
            self.root.destroy()  # 销毁窗口
        except:
            pass
        
        # 第三步：使用 os._exit 确保立即退出
        # 这会终止所有线程，确保程序一定能退出
        import os
        os._exit(0)
               


    def _init_ui(self):
        """初始化UI - 日志面板宽度180-360，智能伸缩"""
        
        # ========== 左侧主内容区域 ==========
        self.left_content = Frame(self.root, bg="white")
        self.left_content.pack(side='left', fill='both', expand=True)
        
        # ========== 状态栏（最底部）==========
        self.status_bar = Label(self.left_content, text="状态: 就绪", bg="#e0e0e0", fg="#333",
                            font=("微软雅黑", 9), anchor='w', padx=10, height=1)
        self.status_bar.pack(fill='x', side='bottom')
        
        # ========== 菜单栏区域（最顶部）==========
        menu_frame = Frame(self.left_content, bg="white", height=50)
        menu_frame.pack(fill='x', side='top')
        menu_frame.pack_propagate(False)
        
        menu_left = Frame(menu_frame, bg="white")
        menu_left.pack(side='left', padx=10, anchor='n', pady=5)
        
        # 文件菜单
        btn_file = Button(menu_left, text="文件", bg="white", fg="#333", relief="flat",
                        font=("微软雅黑", 10), padx=10, command=self._show_file_menu)
        btn_file.pack(side='left')
        self.btn_file = btn_file  # 保存引用用于定位菜单

        # 编辑菜单
        btn_edit = Button(menu_left, text="编辑", bg="white", fg="#333", relief="flat",
                        font=("微软雅黑", 10), padx=10, command=self._show_settings_window)
        btn_edit.pack(side='left')

        # 帮助菜单 - 点击弹出子菜单
        btn_help = Button(menu_left, text="帮助", bg="white", fg="#333", relief="flat",
                        font=("微软雅黑", 10), padx=10, command=self._show_help_menu)
        btn_help.pack(side='left')
        self.btn_help = btn_help  # 保存引用用于定位菜单
        
        gpu_info = self.gpu.info
        if gpu_info["has_discrete"]:
            gpu_text = f"GPU加速: {self.gpu.get_short_status()}"
        elif gpu_info["has_integrated"]:
            gpu_text = f"核显加速: {self.gpu.get_short_status()}"
        else:
            gpu_text = f"CPU模式 ({gpu_info['cores']}核心)"
        
        gpu_label = Label(menu_frame, text=gpu_text, bg="white", fg="#666", font=("微软雅黑", 9))
        gpu_label.pack(side='left', padx=50, anchor='n', pady=8)
        
        resource_frame = Frame(menu_frame, bg="white")
        resource_frame.pack(side='right', padx=10, anchor='n', pady=2)
        
        resource_row1 = Frame(resource_frame, bg="white")
        resource_row1.pack()
        
        Label(resource_row1, text="资源:", bg="white", fg="#666", 
            font=("微软雅黑", 9)).pack(side='left')
        
        self.resource_var = DoubleVar(value=0.7)
        self.resource_scale = Scale(resource_row1, from_=0.3, to=1.0, resolution=0.1,
                                orient=HORIZONTAL, variable=self.resource_var,
                                bg="white", highlightthickness=0, length=160,
                                showvalue=False, troughcolor="#ddd")
        self.resource_scale.pack(side='left', padx=5)
        
        self.resource_label = Label(resource_row1, text="70%", bg="white", fg="#4CAF50",
                                font=("微软雅黑", 9, "bold"))
        self.resource_label.pack(side='left')
        
        resource_tip = Label(resource_frame, text="调整处理占用的系统资源比例", 
                            bg="white", fg="#999", font=("微软雅黑", 8))
        resource_tip.pack()
        
        def update_resource(*args):
            self.resource_label.config(text=f"{int(self.resource_var.get()*100)}%")
        self.resource_var.trace_add("write", update_resource)
        
        # ========== 工具栏 ==========
        toolbar = Frame(self.left_content, bg="white", height=40)
        toolbar.pack(fill='x', side='top')
        toolbar.pack_propagate(False)
        
        toolbar_inner = Frame(toolbar, bg="white")
        toolbar_inner.pack(side='left', padx=5, pady=5)
        
        btn_style = {"bg": "white", "fg": "#333", "relief": "flat", "font": ("微软雅黑", 10),
                    "activebackground": "#f0f0f0"}
        
        Button(toolbar_inner, text="＋ 添加任务", command=self._add_task, **btn_style).pack(side='left', padx=5)
        Button(toolbar_inner, text="－ 移除所选任务", command=self._remove_selected, **btn_style).pack(side='left', padx=5)
        Button(toolbar_inner, text="🗑 清除所有任务", command=self._clear_all, **btn_style).pack(side='left', padx=5)
        
        # ========== 灰色分隔条 ==========
        Frame(self.left_content, bg="#d0d0d0", height=1).pack(fill='x', side='top')
        
        # ========== 中间容器（包含任务列表区域 + 底部控制栏 + 日志面板）==========
        self.middle_container = Frame(self.left_content, bg="white")
        self.middle_container.pack(fill='both', expand=True, side='top')
        
        # ========== 右侧日志面板（放在middle_container内）==========
        self.log_panel = Frame(self.middle_container, bg="white")
        self.log_visible = False
        
        log_header = Frame(self.log_panel, bg="#e8e8e8", height=35)
        log_header.pack(fill='x')
        log_header.pack_propagate(False)
        
        Label(log_header, text="日志", bg="#e8e8e8", fg="#333", 
            font=("微软雅黑", 10, "bold")).pack(side='left', padx=8, pady=5)
        
        Button(log_header, text="✕", command=self._toggle_log, bg="#e8e8e8", fg="#666",
            relief="flat", font=("微软雅黑", 10), width=3).pack(side='right', padx=5)
        
        log_level_frame = Frame(self.log_panel, bg="white")
        log_level_frame.pack(fill='x', padx=5, pady=3)
        
        Label(log_level_frame, text="等级", bg="white", fg="#666",
            font=("微软雅黑", 9)).pack(side='left')
        
        self.log_level = StringVar(value="info")
        from tkinter.ttk import Combobox
        level_combo = Combobox(log_level_frame, textvariable=self.log_level,
                            values=["debug", "info", "warning", "error"], width=8)
        level_combo.pack(side='right')
        
        log_text_frame = Frame(self.log_panel, bg="white")
        log_text_frame.pack(fill='both', expand=True, padx=5, pady=3)
        
        self.log_text = Text(log_text_frame, bg="white", fg="#333", font=("Consolas", 9),
                            wrap='word', relief="solid", bd=1)
        log_scroll = Scrollbar(log_text_frame, orient=VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        
        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)
        
        Button(self.log_panel, text="保存日志", command=self._save_log, bg="white", fg="#333",
            relief="flat", font=("微软雅黑", 9), bd=1, highlightbackground="#ddd").pack(fill='x', padx=5, pady=5)
        
        # ========== 左侧内容区（任务列表+底部控制栏）==========
        self.left_main = Frame(self.middle_container, bg="white")
        self.left_main.pack(side='left', fill='both', expand=True)
        
        # ========== 底部控制栏 ==========
        self.bottom_frame = Frame(self.left_main, bg="#f5f5f5", height=140)
        self.bottom_frame.pack(fill='x', side='bottom')
        self.bottom_frame.pack_propagate(False)

        # 按钮行（在框外面）
        btn_row = Frame(self.bottom_frame, bg="#f5f5f5")
        btn_row.pack(fill='x', pady=(10, 5), padx=10)
        btn_row.columnconfigure(1, weight=1)

        self.btn_stats = Button(btn_row, text="ⓘ 统计数据", command=self._show_stats, 
                            bg="white", fg="#333", relief="solid", bd=1, 
                            font=("微软雅黑", 11, "bold"), width=12)
        self.btn_stats.grid(row=0, column=0, sticky='w')

        self.btn_frame_center = Frame(btn_row, bg="#f5f5f5")
        self.btn_frame_center.grid(row=0, column=1, sticky='ew', padx=10)

        self.btn_start = Button(self.btn_frame_center, text="▷ 开始", command=self._start_processing,
                            bg="white", fg="#333", relief="solid", bd=1,
                            font=("微软雅黑", 12, "bold"))
        self.btn_start.pack(fill='x', expand=True)

        self.btn_pause = Button(self.btn_frame_center, text="❚❚ 暂停", command=self._pause_processing,
                            bg="white", fg="#333", relief="solid", bd=1,
                            font=("微软雅黑", 12, "bold"))

        self.btn_stop = Button(self.btn_frame_center, text="□ 停止", command=self._stop_processing,
                            bg="white", fg="#333", relief="solid", bd=1,
                            font=("微软雅黑", 12, "bold"))

        self.btn_log = Button(btn_row, text="≡ 日志", command=self._toggle_log,
                            bg="white", fg="#333", relief="solid", bd=1,
                            font=("微软雅黑", 11, "bold"), width=10)
        self.btn_log.grid(row=0, column=2, sticky='e')

        # 带边框的统计信息区域（只包含时间和进度条）
        stats_box = LabelFrame(self.bottom_frame, text="", bg="#f5f5f5", 
                            relief="groove", bd=2, padx=10, pady=8)
        stats_box.pack(fill='x', padx=10, pady=(0, 8))

        # 统计信息行
        stats_row = Frame(stats_box, bg="#f5f5f5")
        stats_row.pack(fill='x')

        self.stats_left = Frame(stats_row, bg="#f5f5f5")
        self.stats_left.pack(side='left')

        self.lbl_fps = Label(self.stats_left, text="帧/秒:  -", bg="#f5f5f5", fg="#333",
                            font=("微软雅黑", 9))
        self.lbl_fps.pack(anchor='w')

        self.lbl_elapsed = Label(self.stats_left, text="已用时间:  00:00:00", bg="#f5f5f5", fg="#333",
                                font=("微软雅黑", 9))
        self.lbl_elapsed.pack(anchor='w')

        self.lbl_remaining = Label(self.stats_left, text="剩余时间:  00:00:00", bg="#f5f5f5", fg="#333",
                                font=("微软雅黑", 9))
        self.lbl_remaining.pack(anchor='w')

        # 进度条区域 - 使用Canvas实现
        progress_frame = Frame(stats_row, bg="#f5f5f5")
        progress_frame.pack(side='left', fill='x', expand=True, padx=20)

        # Canvas进度条，高度30
        self.main_progress_canvas = Canvas(progress_frame, bg="#E0E0E0", highlightthickness=1,
                                        highlightbackground="#CCCCCC", height=30)
        self.main_progress_canvas.pack(fill='x', pady=5)
        self.main_progress_canvas.bind('<Configure>', lambda e: self._draw_main_progress())

        # 存储当前进度信息
        self.main_progress_value = 0
        self.main_progress_text = "正在处理: 0/0 (0%)"
        
        # ========== 主区域（任务列表）==========
        self.main_area = Frame(self.left_main, bg="white")
        self.main_area.pack(fill='both', expand=True, side='top')
        
        # 任务列表容器 - 使用统一的容器来确保表头和内容宽度一致
        self.list_container = Frame(self.main_area, bg="white")
        self.list_container.pack(side='left', fill='both', expand=True)
        
        # ========== 表头 - 使用place布局确保列宽固定比例 ==========
        # 表头外层容器
        self.header_container = Frame(self.list_container, bg="white", height=35)
        self.header_container.pack(fill='x', side='top')
        self.header_container.pack_propagate(False)
        
        # 表头内容区（左侧，与数据区域对齐）
        self.header_frame = Frame(self.header_container, bg="white")
        self.header_frame.pack(side='left', fill='both', expand=True)
        
        # 表头右侧占位符（与滚动条同宽，保持对齐）
        self.header_scrollbar_placeholder = Frame(self.header_container, bg="white", width=17)
        self.header_scrollbar_placeholder.pack(side='right', fill='y')
        self.header_scrollbar_placeholder.pack_propagate(False)
        
        # 表头使用place布局，按比例定位
        x_pos = 0.0
        for i, name in enumerate(self.COLUMN_NAMES):
            width = self.COLUMN_WIDTHS[i]
            header_cell = Frame(self.header_frame, bg="white", highlightbackground="#d0d0d0",
                            highlightthickness=1)
            header_cell.place(relx=x_pos, rely=0, relwidth=width, relheight=1.0)
            Label(header_cell, text=name, bg="white", fg="#333", 
                font=("微软雅黑", 10, "bold")).pack(expand=True, pady=5)
            x_pos += width
        
        Frame(self.list_container, bg="#d0d0d0", height=1).pack(fill='x', side='top')
        
        # ========== 任务列表区域 ==========
        self.list_frame = Frame(self.list_container, bg="white")
        self.list_frame.pack(side='top', fill='both', expand=True)
        
        self.drop_hint_frame = Frame(self.list_frame, bg="white")
        
        self.drop_icon = Canvas(self.drop_hint_frame, width=100, height=90, bg="white", highlightthickness=0)
        self.drop_icon.create_rectangle(15, 10, 85, 70, outline="#bbb", dash=(5, 3), width=2)
        self.drop_icon.create_polygon(25, 60, 45, 35, 55, 50, 75, 25, 75, 60, fill="#ccc", outline="#ccc")
        self.drop_icon.create_oval(30, 20, 42, 32, fill="#ccc", outline="#ccc")
        
        self.drop_hint_label = Label(self.drop_hint_frame, text="将文件拖拽到此处以创建新任务",
                                    bg="white", fg="#888", font=("微软雅黑", 12))
        
        self.task_rows_frame = Frame(self.list_frame, bg="white")
        
        self.task_canvas = Canvas(self.task_rows_frame, bg="white", highlightthickness=0)
        self.task_scrollbar = Scrollbar(self.task_rows_frame, orient=VERTICAL, command=self.task_canvas.yview)
        self.task_inner_frame = Frame(self.task_canvas, bg="white")
        
        self.task_canvas.configure(yscrollcommand=self.task_scrollbar.set)
        
        self.task_scrollbar.pack(side='right', fill='y')
        self.task_canvas.pack(side='left', fill='both', expand=True)
        
        self.task_canvas_window = self.task_canvas.create_window((0, 0), window=self.task_inner_frame, anchor='nw')
        
        def on_frame_configure(event):
            self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all"))
        
        def on_canvas_configure(event):
            self.task_canvas.itemconfig(self.task_canvas_window, width=event.width)
        
        self.task_inner_frame.bind("<Configure>", on_frame_configure)
        self.task_canvas.bind("<Configure>", on_canvas_configure)
        
        self._show_drop_hint()
        
        self.task_ui_items = {}
        
        # 绑定窗口大小变化事件，用于调整日志面板宽度
        self.root.bind('<Configure>', self._on_window_resize)

        def on_frame_configure(event):
            self.task_canvas.configure(scrollregion=self.task_canvas.bbox("all"))
        
        def on_canvas_configure(event):
            self.task_canvas.itemconfig(self.task_canvas_window, width=event.width)
        
        self.task_inner_frame.bind("<Configure>", on_frame_configure)
        self.task_canvas.bind("<Configure>", on_canvas_configure)
        
        self._show_drop_hint()
        
        self.task_ui_items = {}
        
        # 设置窗口默认大小和最小尺寸
        self.root.minsize(400, 450)  # 最小宽度400（比原来850小450）
        
        # 绑定窗口大小变化事件，用于调整日志面板宽度
        self.root.bind('<Configure>', self._on_window_resize)
        self._last_width = 1000  # 记录上次窗口宽度
    
    def _show_drop_hint(self):
        """显示拖放提示"""
        self.task_rows_frame.pack_forget()
        self.drop_hint_frame.pack(fill='both', expand=True)
        self.drop_icon.pack(pady=(100, 10))
        self.drop_hint_label.pack(pady=10)
    
    def _hide_drop_hint(self):
        """隐藏拖放提示"""
        self.drop_hint_frame.pack_forget()
        self.task_rows_frame.pack(fill='both', expand=True)
    
    def _setup_drop(self):
        """设置拖放"""
        if self.dnd_available:
            try:
                from tkinterdnd2 import DND_FILES
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind('<<Drop>>', self._on_drop)
            except:
                pass
    
    def _on_drop(self, event):
        """处理拖放"""
        files = event.data.strip('{}').split('} {')
        video_exts = ('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v')
        
        for f in files:
            f = f.strip()
            if f.lower().endswith(video_exts):
                self._show_new_task_dialog(f)
    
    def _add_task(self):
        """添加任务"""
        files = filedialog.askopenfilenames(
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v"), ("所有文件", "*.*")]
        )
        for f in files:
            self._show_new_task_dialog(f)
    
    def _show_new_task_dialog(self, input_path):
        """显示新建任务对话框 - 修复选中逻辑"""
        dialog = NewTaskDialog(self.root, input_path)
        if dialog.result:
            # 先取消旧的选中状态
            old_selected_id = self.selected_task_id
            if old_selected_id and old_selected_id in self.task_ui_items:
                old_task = self.task_manager.get_task(old_selected_id)
                if old_task:
                    self._update_row_color(old_task, is_selected=False)
            
            # 设置新的选中ID（在刷新之前设置）
            self.selected_task_id = dialog.result.task_id
            
            # 添加任务并刷新列表
            self.task_manager.add_task(dialog.result)
            self._refresh_task_list()
            self._log(f"[info] 添加任务: {os.path.basename(input_path)}")

    
    def _refresh_task_list(self):
        """刷新任务列表显示 - 修复选中状态"""
        for widget in self.task_inner_frame.winfo_children():
            widget.destroy()
        self.task_ui_items.clear()
        
        tasks = self.task_manager.get_all_tasks()
        
        if not tasks:
            self._show_drop_hint()
            return
        
        self._hide_drop_hint()
        
        for i, task in enumerate(tasks):
            self._create_task_row(i + 1, task)
            # 创建行后立即设置正确的颜色（包括选中状态）
            is_selected = (self.selected_task_id == task.task_id)
            self._update_row_color(task, is_selected=is_selected)
    
    # ============================================================
# 进度列显示修复 - 替换 App 类的 _create_task_row 方法
# ============================================================

    def _create_task_row(self, index, task):
        """创建任务行 - 使用Canvas实现进度条，文字透明背景自然叠加"""
        row_height = 40
        
        row_frame = Frame(self.task_inner_frame, bg="white", height=row_height)
        row_frame.pack(fill='x', side='top')
        row_frame.pack_propagate(False)
        
        columns_data = [
            (f"{index}  {task.get_filename()}", 'center'),
            (task.get_process_types(), 'center'),
            (None, 'center'),  # 进度列特殊处理
            ("✎", 'center'),
            ("🗑", 'center'),
        ]
        
        cells = []
        progress_canvas = None
        x_pos = 0.0
        
        for col_idx, (text, anchor) in enumerate(columns_data):
            width = self.COLUMN_WIDTHS[col_idx]
            
            cell = Frame(row_frame, bg="white", highlightbackground="#e0e0e0", highlightthickness=1)
            cell.place(relx=x_pos, rely=0, relwidth=width, relheight=1.0)
            
            if col_idx == 2:  # 进度列 - 使用Canvas
                # Canvas背景色就是"未完成"区域的颜色
                progress_canvas = Canvas(cell, bg="#E8E8E8", highlightthickness=0)
                progress_canvas.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
                progress_canvas.bind('<Button-1>', lambda e, t=task: self._select_task(t))
                progress_canvas.bind('<Configure>', lambda e, t=task: self._draw_progress(t))
                
            elif col_idx == 3:  # 编辑按钮
                btn = Button(cell, text=text, bg="white", fg="#666", relief="flat",
                            font=("微软雅黑", 12), cursor="hand2",
                            command=lambda t=task: self._edit_task(t))
                btn.place(relx=0.5, rely=0.5, anchor='center')
            elif col_idx == 4:  # 删除按钮
                btn = Button(cell, text=text, bg="white", fg="#666", relief="flat",
                            font=("微软雅黑", 12), cursor="hand2",
                            command=lambda t=task: self._delete_task(t))
                btn.place(relx=0.5, rely=0.5, anchor='center')
            else:
                lbl = Label(cell, text=text, bg="white", fg="#333", font=("微软雅黑", 9),
                        anchor='center')
                lbl.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
                lbl.bind('<Button-1>', lambda e, t=task: self._select_task(t))
                cell.bind('<Button-1>', lambda e, t=task: self._select_task(t))
            
            cells.append(cell)
            x_pos += width
        
        sep = Frame(self.task_inner_frame, bg="#e0e0e0", height=1)
        sep.pack(fill='x', side='top')
        
        # 只保存 progress_canvas，不再需要 progress_bar 和 progress_label
        self.task_ui_items[task.task_id] = {
            'row_frame': row_frame,
            'cells': cells,
            'separator': sep,
            'progress_canvas': progress_canvas,
        }
        
        self._update_row_color(task)
        
        if progress_canvas:
            self.root.after(10, lambda: self._draw_progress(task))

    def _draw_progress(self, task):
        """绘制进度条和文字 - 文字使用create_text，天然透明背景"""
        if task.task_id not in self.task_ui_items:
            return
        
        ui = self.task_ui_items[task.task_id]
        canvas = ui.get('progress_canvas')
        if not canvas:
            return
        
        # 清除之前的绘制内容
        canvas.delete("all")
        
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        # 计算进度比例和宽度
        progress_ratio = task.progress / 100.0 if task.progress > 0 else 0
        progress_ratio = max(0, min(progress_ratio, 1.0))
        progress_width = int(width * progress_ratio)
        
        # 根据任务状态确定进度条颜色
        if task.status == TaskStatus.COMPLETED or task.progress >= 100:
            bar_color = self.PROGRESS_COLORS["completed"]
        elif task.status == TaskStatus.PAUSED:
            bar_color = self.PROGRESS_COLORS["paused"]
        elif task.status == TaskStatus.STOPPED:
            bar_color = self.PROGRESS_COLORS["stopped"]
        else:
            bar_color = self.PROGRESS_COLORS["running"]
        
        # 第一层：绘制进度条矩形（Canvas背景#E8E8E8是未完成区域）
        if progress_width > 0:
            canvas.create_rectangle(0, 0, progress_width, height, fill=bar_color, outline="")
        
        # 第二层：绘制文字（create_text没有背景，自然透明叠加）
        text = task.get_progress_text()
        text_x = width // 2
        text_y = height // 2
        
        # 文字颜色：当进度条覆盖文字中心时切换为白色
        text_color = "white" if progress_width > text_x else "#333333"
        
        canvas.create_text(text_x, text_y, text=text, fill=text_color,
                        font=("微软雅黑", 11, "bold"))

    def _draw_main_progress(self):
        """绘制底部主进度条 - 文字透明背景叠加在进度条上"""
        canvas = self.main_progress_canvas
        canvas.delete("all")
        
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            return
        
        # 计算进度宽度
        progress_ratio = self.main_progress_value / 100.0
        progress_ratio = max(0, min(progress_ratio, 1.0))
        progress_width = int(width * progress_ratio)
        
        # 绘制进度条（蓝色）
        if progress_width > 0:
            canvas.create_rectangle(0, 0, progress_width, height, fill="#2196F3", outline="")
        
        # 绘制文字（透明背景）
        text_x = width // 2
        text_y = height // 2
        
        # 文字颜色：进度条覆盖文字中心时切换为白色
        text_color = "white" if progress_width > text_x else "#333333"
        
        canvas.create_text(text_x, text_y, text=self.main_progress_text, fill=text_color,
                        font=("微软雅黑", 10, "bold"))

    def _select_task(self, task):
        """选择任务"""
        old_id = self.selected_task_id
        self.selected_task_id = task.task_id
        
        # 更新旧选中行的颜色
        if old_id and old_id in self.task_ui_items:
            old_task = self.task_manager.get_task(old_id)
            if old_task:
                self._update_row_color(old_task, is_selected=False)
        
        # 更新新选中行的颜色
        self._update_row_color(task, is_selected=True)
    
    def _highlight_row(self, task_id, highlight=True):
        """高亮或取消高亮任务行（仅用于选中状态）"""
        task = self.task_manager.get_task(task_id)
        if task:
            self._update_row_color(task, is_selected=highlight)
    
    # ============================================================
    # 同时需要替换 App 类的 _update_row_color 方法（增强版）
    # ============================================================

    def _update_row_color(self, task, is_selected=None):
        """根据任务状态更新行颜色"""
        if task.task_id not in self.task_ui_items:
            return
        
        ui = self.task_ui_items[task.task_id]
        
        if is_selected is None:
            is_selected = (self.selected_task_id == task.task_id)
        
        # 确定背景色
        if task.status == TaskStatus.RUNNING:
            bg_color = self.STATUS_COLORS[TaskStatus.RUNNING]
        elif is_selected:
            bg_color = self.STATUS_COLORS["selected"]
        elif task.status == TaskStatus.PAUSED:
            bg_color = self.STATUS_COLORS[TaskStatus.PAUSED]
        elif task.status == TaskStatus.STOPPED:
            bg_color = self.STATUS_COLORS[TaskStatus.STOPPED]
        elif task.status == TaskStatus.COMPLETED:
            bg_color = self.STATUS_COLORS[TaskStatus.COMPLETED]
        elif task.status == TaskStatus.FAILED:
            bg_color = self.STATUS_COLORS[TaskStatus.FAILED]
        else:
            bg_color = self.STATUS_COLORS[TaskStatus.PENDING]
        
        ui['row_frame'].config(bg=bg_color)
        
        for idx, cell in enumerate(ui['cells']):
            if idx == 2:  # 进度列是Canvas，不改变背景
                continue
            cell.config(bg=bg_color)
            for child in cell.winfo_children():
                if isinstance(child, (Label, Frame)):
                    try:
                        child.config(bg=bg_color)
                    except:
                        pass
        
        # 重绘进度条
        self._draw_progress(task)
        
        # 更新进度条颜色
        progress_bar = ui.get('progress_bar')
        progress_label = ui.get('progress_label')
        
        if progress_bar:
            if task.status == TaskStatus.COMPLETED or task.progress >= 100:
                bar_color = self.PROGRESS_COLORS["completed"]
            elif task.status == TaskStatus.PAUSED:
                bar_color = self.PROGRESS_COLORS["paused"]
            elif task.status == TaskStatus.STOPPED:
                bar_color = self.PROGRESS_COLORS["stopped"]
            else:
                bar_color = self.PROGRESS_COLORS["running"]
            
            progress_bar.config(bg=bar_color)
            
            # 更新进度条文本的背景色（根据进度位置）
            if progress_label:
                progress_ratio = task.progress / 100.0 if task.progress > 0 else 0
                if progress_ratio > 0.5:
                    progress_label.config(bg=bar_color, fg="white")
                else:
                    progress_label.config(bg="#E8E8E8", fg="#333333")
    
    def _edit_task(self, task):
        """编辑任务"""
        if task.status == TaskStatus.RUNNING:
            messagebox.showwarning("提示", "任务正在运行，无法编辑")
            return
        
        dialog = NewTaskDialog(self.root, task.input_path, existing_task=task)
        if dialog.result:
            for key, value in dialog.result.__dict__.items():
                if hasattr(task, key) and key != 'task_id':
                    setattr(task, key, value)
            self._refresh_task_list()
    
    def _delete_task(self, task):
        """删除任务"""
        if task.status == TaskStatus.RUNNING:
            messagebox.showwarning("提示", "任务正在运行，无法删除")
            return
        
        self.task_manager.remove_task(task.task_id)
        if self.selected_task_id == task.task_id:
            self.selected_task_id = None
        self._refresh_task_list()
    
    def _remove_selected(self):
        """移除选中的任务"""
        if self.selected_task_id:
            task = self.task_manager.get_task(self.selected_task_id)
            if task:
                self._delete_task(task)
        else:
            messagebox.showinfo("提示", "请先选择一个任务")
    
    def _clear_all(self):
        """清除所有任务"""
        if self.is_running:
            messagebox.showwarning("提示", "有任务正在运行")
            return
        self.task_manager.clear_all()
        self.selected_task_id = None
        self._refresh_task_list()
    
    def _toggle_log(self):
        """切换日志面板 - 智能扩展窗口宽度"""
        if self.log_visible:
            # ===== 收起日志面板 =====
            self.log_panel.pack_forget()
            self.log_visible = False
            # 恢复主窗口最小宽度为不含日志的宽度
            self.root.minsize(self.main_min_width, self.min_height)
        else:
            # ===== 展开日志面板 =====
            current_width = self.root.winfo_width()
            current_height = self.root.winfo_height()
            
            # 计算含日志面板时的最小窗口宽度
            min_with_log = self.main_min_width + self.log_min_width  # 400 + 180 = 580
            
            # 计算需要扩展的宽度
            if current_width < min_with_log:
                # 需要扩展窗口
                new_width = min_with_log
                self.root.geometry(f"{new_width}x{current_height}")
                # 等待窗口更新后再计算日志面板宽度
                self.root.update_idletasks()
                current_width = new_width
            
            # 设置主窗口最小宽度（含日志面板时）
            self.root.minsize(min_with_log, self.min_height)
            
            # 计算日志面板宽度
            available_for_log = current_width - self.main_min_width
            
            # 日志面板宽度在 log_min_width 和 log_max_width 之间
            log_width = max(self.log_min_width, min(self.log_max_width, available_for_log))
            
            self.log_panel.config(width=log_width)
            self.log_panel.pack_propagate(False)
            self.log_panel.pack(side='right', fill='y', before=self.left_main)
            self.log_visible = True    
    
    def _on_window_resize(self, event):
        """窗口大小变化时调整日志面板宽度"""
        # 只处理根窗口的Configure事件
        if event.widget != self.root:
            return
        
        # 避免频繁更新
        current_width = event.width
        if abs(current_width - self._last_width) < 5:
            return
        self._last_width = current_width
        
        # 如果日志面板可见，根据窗口宽度调整日志面板宽度
        if self.log_visible:
            available_for_log = current_width - self.main_min_width
            
            if available_for_log >= self.log_max_width:
                log_width = self.log_max_width
            elif available_for_log >= self.log_min_width:
                log_width = available_for_log
            else:
                log_width = self.log_min_width
            
            self.log_panel.config(width=log_width)   
    
    def _log(self, msg):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(END, f"[{timestamp}] {msg}\n")
        self.log_text.see(END)
        self.root.update_idletasks()
    
    def _save_log(self):
        """保存日志"""
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                           filetypes=[("文本文件", "*.txt")])
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, END))
    
    def _update_status(self, text):
        """更新状态栏"""
        self.status_bar.config(text=f"状态: {text}")
    
    def _show_stats(self):
        """显示统计数据"""
        total = self.task_manager.get_task_count()
        completed = self.task_manager.get_completed_count()
        messagebox.showinfo("统计数据", f"总任务: {total}\n已完成: {completed}")
    
    def _start_processing(self):
        """开始处理"""
        global STOP_FLAG, PAUSE_FLAG
        
        if self.is_running:
            return
        
        # 检查FFmpeg是否可用
        if not PM.is_exe_available("ffmpeg"):
            result = messagebox.askyesno(
                "缺少FFmpeg", 
                "检测到FFmpeg未安装，无法处理视频。\n\n是否打开帮助窗口下载安装FFmpeg？"
            )
            if result:
                self._show_activation_window()
            return
        
        task = self.task_manager.get_next_task()
        if not task:
            messagebox.showinfo("提示", "没有待处理的任务")
            return
        
        STOP_FLAG = False
        PAUSE_FLAG = False
        self.is_running = True
        self.is_paused = False
        
        self.btn_start.pack_forget()
        self.btn_pause.pack(side='left', fill='x', expand=True, padx=(0, 5))
        self.btn_stop.pack(side='left', fill='x', expand=True, padx=(5, 0))
        
        # 根据设置自动显示统计数据
        if self.setting_auto_show_stats.get():
            self._show_stats()
        
        threading.Thread(target=self._process_tasks, daemon=True).start()
    
    def _pause_processing(self):
        """暂停/继续处理"""
        global PAUSE_FLAG
        
        if self.is_paused:
            PAUSE_FLAG = False
            self.is_paused = False
            self.btn_pause.config(text="❚❚ 暂停")
            if self.current_processing_task:
                self.current_processing_task.status = TaskStatus.RUNNING
        else:
            PAUSE_FLAG = True
            self.is_paused = True
            self.btn_pause.config(text="▷ 继续")
            if self.current_processing_task:
                self.current_processing_task.status = TaskStatus.PAUSED
        
        self._refresh_task_list()
    
    def _stop_processing(self):
        """停止处理"""
        global STOP_FLAG
        STOP_FLAG = True
        
        if self.current_processing_task:
            self.current_processing_task.status = TaskStatus.STOPPED
        
        self._finish_processing()
    
    def _finish_processing(self):
        """完成处理"""
        self.is_running = False
        self.is_paused = False
        self.current_processing_task = None
        
        self.btn_pause.pack_forget()
        self.btn_stop.pack_forget()
        self.btn_start.pack(fill='x', expand=True)
        
        self._refresh_task_list()
    
    def _process_tasks(self):
        """处理所有任务"""
        global STOP_FLAG
        
        while not STOP_FLAG:
            task = self.task_manager.get_next_task()
            if not task:
                break
            
            self.current_processing_task = task
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()
            
            self._update_status(f"正在处理文件 {task.input_path}")
            self._log(f"[info] 开始处理: {task.get_filename()}")
            
            self.root.after(0, self._refresh_task_list)
            
            try:
                pipeline = VideoPipeline(task, self._log, self.gpu.info, self.resource_var.get())
                
                def progress_cb(current, total, fps):
                    task.current_frame = current
                    task.total_frames = total
                    task.progress = current / total * 100 if total > 0 else 0
                    task.fps = fps
                    self.root.after(0, lambda: self._update_task_ui(task))
                
                def time_cb(elapsed):
                    task.elapsed_time = elapsed
                    self.root.after(0, lambda: self._update_time_display(task))
                
                frames, elapsed = pipeline.run(progress_cb, time_cb, 
                                              lambda s: self._update_status(s))
                
                if not STOP_FLAG:
                    task.status = TaskStatus.COMPLETED
                    task.progress = 100
                    self._log(f"[info] 完成: {task.get_filename()}, 用时 {self._format_time(elapsed)}")
                    
            except Exception as e:
                task.status = TaskStatus.FAILED
                self._log(f"[error] 处理失败: {e}")
            
            self.root.after(0, self._refresh_task_list)
        
        self.root.after(0, self._on_all_complete)
    
    # ============================================================
# 同时需要替换 App 类的 _update_task_ui 方法
# ============================================================

    def _update_task_ui(self, task):
        """更新任务UI - 任务行进度和底部主进度"""
        if task.task_id in self.task_ui_items:
            self._draw_progress(task)
            self._update_row_color(task)
        
        # 更新底部主进度条
        total = self.task_manager.get_task_count()
        completed = self.task_manager.get_completed_count()
        
        if total > 1:
            # 多任务模式：显示整体进度
            overall = completed / total * 100
            self.main_progress_value = overall
            self.main_progress_text = f"正在处理: {completed}/{total} ({overall:.0f}%)"
        else:
            # 单任务模式：显示当前任务帧进度
            self.main_progress_value = task.progress
            self.main_progress_text = f"正在处理: {task.current_frame}/{task.total_frames} ({task.progress:.0f}%)"
        
        # 重绘底部进度条
        self._draw_main_progress()
        
        self.lbl_fps.config(text=f"帧/秒:  {task.fps:.2f}")
    
    def _update_time_display(self, task):
        """更新时间显示"""
        elapsed = task.elapsed_time
        self.lbl_elapsed.config(text=f"已用时间:  {self._format_time(elapsed)}")
        
        if task.fps > 0 and task.total_frames > 0:
            remaining_frames = task.total_frames - task.current_frame
            remaining_time = remaining_frames / task.fps
            self.lbl_remaining.config(text=f"剩余时间:  {self._format_time(remaining_time)}")
    
    def _format_time(self, seconds):
        """格式化时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _on_all_complete(self):
        """所有任务完成"""
        self._finish_processing()
        
        # 重置底部进度条显示
        self.main_progress_value = 100
        self.main_progress_text = "处理完成"
        self._draw_main_progress()
        
        # 根据设置删除已完成任务
        if self.setting_delete_completed.get():
            completed_tasks = [t for t in list(self.task_manager.tasks.values()) 
                            if t.status == TaskStatus.COMPLETED]
            for task in completed_tasks:
                self.task_manager.remove_task(task.task_id)
            self._refresh_task_list()
            self._log(f"[info] 已删除 {len(completed_tasks)} 个已完成的任务")
        
        # 显示完成对话框
        win = Toplevel(self.root)
        win.title("处理已完成")
        win.geometry("350x180")
        win.configure(bg="white")
        win.transient(self.root)
        
        Label(win, text="ⓘ", font=("", 40), bg="white", fg="#2196F3").pack(pady=10)
        Label(win, text="所有视频均已成功处理完成。", bg="white", fg="#333",
            font=("微软雅黑", 11)).pack()
        
        btn_frame = Frame(win, bg="white")
        btn_frame.pack(pady=20)
        
        def open_location():
            completed_tasks = [t for t in self.task_manager.tasks.values() 
                            if t.status == TaskStatus.COMPLETED]
            if completed_tasks:
                folder = os.path.dirname(completed_tasks[0].output_path)
                if sys.platform == 'win32':
                    os.startfile(folder)
                elif sys.platform == 'darwin':
                    subprocess.run(['open', folder])
                else:
                    subprocess.run(['xdg-open', folder])
            win.destroy()
        
        Button(btn_frame, text="文件位置", command=open_location, bg="#2196F3", fg="white",
            font=("微软雅黑", 10), width=10, relief="flat").pack(side='left', padx=10)
        Button(btn_frame, text="OK", command=win.destroy, bg="#4CAF50", fg="white",
            font=("微软雅黑", 10), width=10, relief="flat").pack(side='left', padx=10)
        
        # 根据设置执行完成后操作
        action = self.setting_on_complete.get()
        if action != "nothing":
            win.after(2000, lambda: self._execute_complete_action(action))

    def _execute_complete_action(self, action):
        """执行处理完成后的操作"""
        if action == "nothing":
            return
        
        action_names = {
            "shutdown": "关机",
            "sleep": "睡眠", 
            "hibernate": "休眠"
        }
        
        # 倒计时确认
        confirm_win = Toplevel(self.root)
        confirm_win.title("即将执行操作")
        confirm_win.geometry("350x180")
        confirm_win.configure(bg="white")
        confirm_win.transient(self.root)
        confirm_win.grab_set()
        
        countdown = [30]  # 使用列表以便在闭包中修改
        
        Label(confirm_win, text="⚠️", font=("", 40), bg="white", fg="#FF9800").pack(pady=10)
        
        msg_label = Label(confirm_win, text=f"计算机将在 {countdown[0]} 秒后{action_names.get(action, action)}",
                        bg="white", fg="#333", font=("微软雅黑", 11))
        msg_label.pack()
        
        btn_frame = Frame(confirm_win, bg="white")
        btn_frame.pack(pady=15)
        
        cancelled = [False]
        
        def cancel():
            cancelled[0] = True
            confirm_win.destroy()
            self._log(f"[info] 用户取消了{action_names.get(action, action)}操作")
        
        def do_action():
            confirm_win.destroy()
            self._log(f"[info] 正在执行: {action_names.get(action, action)}")
            
            try:
                if sys.platform == 'win32':
                    if action == "shutdown":
                        subprocess.run(['shutdown', '/s', '/t', '5'], shell=True)
                    elif action == "sleep":
                        # Windows睡眠命令
                        subprocess.run(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0', '1', '0'], shell=True)
                    elif action == "hibernate":
                        subprocess.run(['shutdown', '/h'], shell=True)
                elif sys.platform == 'darwin':  # macOS
                    if action == "shutdown":
                        subprocess.run(['sudo', 'shutdown', '-h', 'now'])
                    elif action == "sleep":
                        subprocess.run(['pmset', 'sleepnow'])
                else:  # Linux
                    if action == "shutdown":
                        subprocess.run(['systemctl', 'poweroff'])
                    elif action == "sleep":
                        subprocess.run(['systemctl', 'suspend'])
                    elif action == "hibernate":
                        subprocess.run(['systemctl', 'hibernate'])
            except Exception as e:
                messagebox.showerror("执行失败", f"无法执行{action_names.get(action, action)}操作:\n{e}")
        
        Button(btn_frame, text="取消", command=cancel, bg="#F44336", fg="white",
            font=("微软雅黑", 10, "bold"), width=12, relief="flat").pack(side='left', padx=10)
        
        Button(btn_frame, text="立即执行", command=do_action, bg="#FF9800", fg="white",
            font=("微软雅黑", 10), width=12, relief="flat").pack(side='left', padx=10)
        
        def update_countdown():
            if cancelled[0] or not confirm_win.winfo_exists():
                return
            countdown[0] -= 1
            if countdown[0] <= 0:
                do_action()
            else:
                msg_label.config(text=f"计算机将在 {countdown[0]} 秒后{action_names.get(action, action)}")
                confirm_win.after(1000, update_countdown)
        
        confirm_win.after(1000, update_countdown)
    
    def _show_file_menu(self):
        """显示文件菜单"""
        # 创建弹出菜单
        menu = Toplevel(self.root)
        menu.overrideredirect(True)  # 无边框窗口
        menu.configure(bg="white", relief="solid", bd=1)
        
        # 获取按钮位置
        x = self.btn_file.winfo_rootx()
        y = self.btn_file.winfo_rooty() + self.btn_file.winfo_height()
        menu.geometry(f"+{x}+{y}")
        
        # 菜单项样式
        menu_style = {"bg": "white", "fg": "#333", "relief": "flat", 
                    "font": ("微软雅黑", 10), "anchor": "w", "padx": 20, "pady": 8,
                    "activebackground": "#e3f2fd", "activeforeground": "#1976d2"}
        
        # 退出按钮
        btn_exit = Button(menu, text="🚪 退出", width=15,
                        command=lambda: [menu.destroy(), self._exit_app()], **menu_style)
        btn_exit.pack(fill='x')
        
        # 点击其他地方关闭菜单
        def close_menu(event):
            try:
                if menu.winfo_exists():
                    widget_str = str(event.widget)
                    menu_str = str(menu)
                    if not widget_str.startswith(menu_str):
                        menu.destroy()
            except:
                pass
        
        self.root.bind('<Button-1>', close_menu, add='+')
        menu.bind('<Leave>', lambda e: self.root.after(300, lambda: menu.destroy() if menu.winfo_exists() else None))
    

    def _exit_app(self):
        """退出程序"""
        if self.is_running:
            # 有任务在运行，询问是否强制退出
            result = messagebox.askyesnocancel(
                "确认退出",
                "当前有任务正在处理中。\n\n"
                "• 点击【是】: 停止任务并退出\n"
                "• 点击【否】: 取消退出，继续处理\n"
                "• 点击【取消】: 取消退出"
            )
            
            if result is True:  # 点击"是"
                global STOP_FLAG
                STOP_FLAG = True
                self._log("[info] 用户请求退出，正在停止任务...")
                
                # 等待任务停止后退出
                def wait_and_exit():
                    if self.is_running:
                        self.root.after(100, wait_and_exit)
                    else:
                        self.root.destroy()
                
                self.root.after(100, wait_and_exit)
            # 点击"否"或"取消"则不做任何操作
        else:
            # 没有任务在运行，直接确认退出
            if messagebox.askyesno("确认退出", "确定要退出程序吗？"):
                self.root.destroy()

    def _show_settings_window(self):
        """显示设置窗口"""
        win = Toplevel(self.root)
        win.title("设置")
        win.geometry("450x500")
        win.configure(bg="white")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        
        # 标题
        Label(win, text="⚙️ 程序设置", bg="white", fg="#333",
            font=("微软雅黑", 14, "bold")).pack(pady=15)
        
        # ===== 其他选项（放在上面）=====
        other_frame = LabelFrame(win, text="其他选项", bg="white", fg="#333",
                                font=("微软雅黑", 10, "bold"), padx=15, pady=10)
        other_frame.pack(fill='x', padx=20, pady=10)
        
        # 自动显示统计数据
        Checkbutton(other_frame, text="📊 当处理开始时自动显示统计数据",
                    variable=self.setting_auto_show_stats, bg="white", fg="#333",
                    font=("微软雅黑", 10), selectcolor="white",
                    activebackground="white").pack(anchor='w', pady=5)
        
        # 删除已完成任务
        Checkbutton(other_frame, text="🗑️ 处理完成后删除已完成的任务",
                    variable=self.setting_delete_completed, bg="white", fg="#333",
                    font=("微软雅黑", 10), selectcolor="white",
                    activebackground="white").pack(anchor='w', pady=5)
        
        # ===== 处理完成后操作（放在下面）=====
        complete_frame = LabelFrame(win, text="处理完成后", bg="white", fg="#333",
                                    font=("微软雅黑", 10, "bold"), padx=15, pady=10)
        complete_frame.pack(fill='x', padx=20, pady=10)
        
        # 下拉选择
        options_frame = Frame(complete_frame, bg="white")
        options_frame.pack(fill='x', pady=5)
        
        Label(options_frame, text="执行操作:", bg="white", fg="#333",
            font=("微软雅黑", 10)).pack(side='left')
        
        # 带序号的选项
        display_options = [
            "1. 什么都不做",
            "2. 关机",
            "3. 睡眠",
            "4. 休眠"
        ]
        
        # 映射关系
        display_to_value = {
            "1. 什么都不做": "nothing",
            "2. 关机": "shutdown",
            "3. 睡眠": "sleep",
            "4. 休眠": "hibernate"
        }
        
        value_to_display = {v: k for k, v in display_to_value.items()}
        
        # 显示用的变量
        self.complete_display_var = StringVar(value=value_to_display.get(self.setting_on_complete.get(), "1. 什么都不做"))
        
        from tkinter.ttk import Combobox
        complete_combo = Combobox(options_frame, textvariable=self.complete_display_var,
                                values=display_options, state="readonly", width=18)
        complete_combo.pack(side='left', padx=10)
        
        # 当选择改变时更新实际值
        def on_combo_change(*args):
            display_val = self.complete_display_var.get()
            actual_val = display_to_value.get(display_val, "nothing")
            self.setting_on_complete.set(actual_val)
        
        self.complete_display_var.trace_add("write", on_combo_change)
        
        # 选项说明
        desc_frame = Frame(complete_frame, bg="white")
        desc_frame.pack(fill='x', pady=(10, 5))
        
        descriptions = [
            ("1. 什么都不做", "处理完成后程序保持运行"),
            ("2. 关机", "处理完成后自动关闭计算机"),
            ("3. 睡眠", "处理完成后计算机进入睡眠模式"),
            ("4. 休眠", "处理完成后计算机进入休眠模式"),
        ]
        
        for name, desc in descriptions:
            row = Frame(desc_frame, bg="white")
            row.pack(fill='x', pady=2)
            Label(row, text=f"• {name}:", bg="white", fg="#333", 
                font=("微软雅黑", 9), width=14, anchor='w').pack(side='left')
            Label(row, text=desc, bg="white", fg="#666",
                font=("微软雅黑", 9)).pack(side='left')
        
        # ===== 按钮区域 =====
        btn_frame = Frame(win, bg="white")
        btn_frame.pack(pady=20)
        
        def save_and_close():
            self._log(f"[info] 设置已保存: 完成后={self.setting_on_complete.get()}, "
                    f"自动统计={self.setting_auto_show_stats.get()}, "
                    f"删除完成={self.setting_delete_completed.get()}")
            win.destroy()
        
        Button(btn_frame, text="✓ 确定", command=save_and_close, bg="#4CAF50", fg="white",
            font=("微软雅黑", 10), relief="flat", width=10).pack(side='left', padx=10)
        
        Button(btn_frame, text="✕ 取消", command=win.destroy, bg="#9E9E9E", fg="white",
            font=("微软雅黑", 10), relief="flat", width=10).pack(side='left', padx=10)

    def _show_help_menu(self):
        """显示帮助子菜单"""
        menu = Toplevel(self.root)
        menu.overrideredirect(True)
        menu.configure(bg="white", relief="solid", bd=1)
        
        # 获取按钮位置
        x = self.btn_help.winfo_rootx()
        y = self.btn_help.winfo_rooty() + self.btn_help.winfo_height()
        menu.geometry(f"+{x}+{y}")
        
        menu_style = {"bg": "white", "fg": "#333", "relief": "flat",
                    "font": ("微软雅黑", 10), "anchor": "w", "padx": 20, "pady": 8,
                    "activebackground": "#e3f2fd", "activeforeground": "#1976d2"}
        
        def on_activation():
            menu.destroy()
            self._show_activation_window()
        
        def on_usage():
            menu.destroy()
            self._show_usage_guide()
        
        def on_about():
            menu.destroy()
            self._show_about_window()
        
        Button(menu, text="🔐 软件激活", width=15, command=on_activation, **menu_style).pack(fill='x')
        Button(menu, text="📖 使用说明", width=15, command=on_usage, **menu_style).pack(fill='x')
        Button(menu, text="ℹ️ 关于", width=15, command=on_about, **menu_style).pack(fill='x')
        
        # 点击菜单外部时关闭菜单
        def close_menu(event):
            try:
                if not menu.winfo_exists():
                    return
                # 获取点击位置
                click_x = event.x_root
                click_y = event.y_root
                # 获取菜单位置和大小
                menu_x = menu.winfo_rootx()
                menu_y = menu.winfo_rooty()
                menu_w = menu.winfo_width()
                menu_h = menu.winfo_height()
                # 如果点击在菜单外部，关闭菜单
                if not (menu_x <= click_x <= menu_x + menu_w and menu_y <= click_y <= menu_y + menu_h):
                    menu.destroy()
                    # 解除绑定
                    try:
                        self.root.unbind('<Button-1>')
                    except:
                        pass
            except:
                pass
        
        # 延迟绑定，避免立即触发
        self.root.after(100, lambda: self.root.bind('<Button-1>', close_menu))
        
        # 菜单失去焦点时关闭（但不使用 Leave 事件，因为它太敏感）
        menu.bind('<FocusOut>', lambda e: self.root.after(200, lambda: menu.destroy() if menu.winfo_exists() else None))

    def _show_activation_window(self):
        """显示软件激活窗口"""
        win = Toplevel(self.root)
        win.title("软件激活")
        win.geometry("420x450")
        win.configure(bg="white")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)
        
        # 居中显示
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        win_w, win_h = 420, 450
        x = main_x + (main_w - win_w) // 2
        y = main_y + (main_h - win_h) // 2
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # 标题
        Label(win, text="🔐 软件激活", bg="white", fg="#333",
            font=("微软雅黑", 14, "bold")).pack(pady=15)
        
        # 激活状态区域
        status_frame = LabelFrame(win, text="激活状态", bg="white", fg="#333",
                                font=("微软雅黑", 10, "bold"), padx=15, pady=10)
        status_frame.pack(fill='x', padx=20, pady=10)
        
        if self.activated:
            status_text = "✅ 软件已激活"
            status_color = "#4CAF50"
        else:
            remaining = getattr(self, 'trial_mins', 15)
            status_text = f"⚠️ 软件未激活 (试用剩余: {remaining}分钟)"
            status_color = "#FF9800"
        
        status_label = Label(status_frame, text=status_text, bg="white", fg=status_color,
                            font=("微软雅黑", 12, "bold"))
        status_label.pack(anchor='w', pady=5)
        
        # 机器码
        Label(status_frame, text="📋 机器码:", bg="white", fg="#333",
            font=("微软雅黑", 10)).pack(anchor='w', pady=(10, 2))
        
        mac_frame = Frame(status_frame, bg="white")
        mac_frame.pack(fill='x', pady=2)
        
        mac_entry = Entry(mac_frame, width=30, font=("Consolas", 11), justify="center",
                        relief="solid", bd=1)
        mac_entry.pack(side='left', ipady=4)
        mac_entry.insert(0, self.mac)
        mac_entry.config(state='readonly')
        
        def copy_mac():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.mac)
            messagebox.showinfo("复制成功", "机器码已复制到剪贴板")
        
        Button(mac_frame, text="复制", command=copy_mac, bg="#2196F3", fg="white",
            font=("微软雅黑", 9), relief="flat", width=6).pack(side='left', padx=10)
        
        # 激活密钥输入（仅未激活时显示）
        if not self.activated:
            Label(status_frame, text="🔑 激活密钥:", bg="white", fg="#333",
                font=("微软雅黑", 10)).pack(anchor='w', pady=(15, 2))
            
            key_frame = Frame(status_frame, bg="white")
            key_frame.pack(fill='x', pady=2)
            
            key_entry = Entry(key_frame, width=30, font=("Consolas", 11),
                            justify="center", relief="solid", bd=1)
            key_entry.pack(side='left', ipady=4)
            
            def do_activate():
                if LicenseManager.verify_key(self.mac, key_entry.get()):
                    LicenseManager.save_license()
                    self.activated = True
                    self.root.title("笔记本高清视频修复 2025 V7.0")
                    status_label.config(text="✅ 软件已激活", fg="#4CAF50")
                    messagebox.showinfo("成功", "✅ 激活成功！")
                    key_frame.pack_forget()
                    activate_btn.pack_forget()
                else:
                    messagebox.showerror("错误", "❌ 密钥无效，请检查后重试")
            
            activate_btn = Button(status_frame, text="✅ 立即激活", command=do_activate,
                                bg="#4CAF50", fg="white", font=("微软雅黑", 10, "bold"),
                                relief="flat", width=15)
            activate_btn.pack(pady=10)
        
        # FFmpeg检测区域
        ffmpeg_frame = LabelFrame(win, text="🛠️ FFmpeg 环境", bg="white", fg="#333",
                                font=("微软雅黑", 10, "bold"), padx=15, pady=10)
        ffmpeg_frame.pack(fill='x', padx=20, pady=10)
        
        ffmpeg_path = PM.get_exe("ffmpeg")
        is_available = PM.is_exe_available("ffmpeg")
        
        if is_available:
            ffmpeg_status = "✅ FFmpeg 已安装"
            ffmpeg_color = "#4CAF50"
        else:
            ffmpeg_status = "❌ FFmpeg 未安装"
            ffmpeg_color = "#F44336"
        
        Label(ffmpeg_frame, text=ffmpeg_status, bg="white", fg=ffmpeg_color,
            font=("微软雅黑", 10)).pack(anchor='w')
        
        if is_available:
            Label(ffmpeg_frame, text=f"路径: {ffmpeg_path}", bg="white", fg="#666",
                font=("微软雅黑", 9)).pack(anchor='w')
        else:
            def download_ffmpeg():
                self._download_ffmpeg_from_activation(win, ffmpeg_frame)
            
            Button(ffmpeg_frame, text="📥 下载安装 FFmpeg", command=download_ffmpeg,
                bg="#FF9800", fg="white", font=("微软雅黑", 10),
                relief="flat").pack(pady=5)
        
        # 客服信息
        Label(win, text="💬 获取密钥请联系客服: u788990@163.com",
            bg="white", fg="#666", font=("微软雅黑", 9)).pack(pady=10)
        
        # 关闭按钮
        Button(win, text="关闭", command=win.destroy, bg="#9E9E9E", fg="white",
            font=("微软雅黑", 10), relief="flat", width=12).pack(pady=10)

    def _download_ffmpeg_from_activation(self, parent_win, ffmpeg_frame):
        """从激活窗口下载FFmpeg"""
        if PM.is_exe_available("ffmpeg"):
            messagebox.showinfo("提示", "FFmpeg 已经安装，无需重复下载")
            return
        
        # 创建进度显示
        progress_frame = Frame(ffmpeg_frame, bg="white")
        progress_frame.pack(fill='x', pady=5)
        
        progress_label = Label(progress_frame, text="准备下载...", bg="white", fg="#333",
                            font=("微软雅黑", 9))
        progress_label.pack(anchor='w')
        
        progress_bar = Progressbar(progress_frame, length=300, mode='determinate')
        progress_bar.pack(fill='x', pady=5)
        
        def update_progress(percent):
            progress_bar['value'] = percent
            progress_label.config(text=f"下载进度: {percent:.1f}%")
            self.root.update_idletasks()
        
        def download_thread():
            try:
                self.root.after(0, lambda: progress_label.config(text="正在下载FFmpeg..."))
                success = self.downloader.download_component("ffmpeg", progress_cb=update_progress)
                
                if success:
                    PM.refresh()
                    self.root.after(0, lambda: [
                        progress_label.config(text="✅ FFmpeg 安装成功!"),
                        messagebox.showinfo("成功", "FFmpeg 安装成功！")
                    ])
                else:
                    self.root.after(0, lambda: [
                        progress_label.config(text="❌ 下载失败，请检查网络"),
                        messagebox.showerror("失败", "下载失败，请检查网络连接")
                    ])
            except Exception as e:
                self.root.after(0, lambda: progress_label.config(text=f"❌ 错误: {str(e)[:30]}"))
        
        threading.Thread(target=download_thread, daemon=True).start()

    def _show_usage_guide(self):
        """显示使用说明窗口"""
        win = Toplevel(self.root)
        win.title("使用说明")
        win.geometry("550x600")
        win.configure(bg="white")
        win.transient(self.root)
        win.resizable(False, False)
        
        # 居中显示
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        win_w, win_h = 550, 600
        x = main_x + (main_w - win_w) // 2
        y = main_y + (main_h - win_h) // 2
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # 标题
        Label(win, text="📖 使用说明", bg="white", fg="#333",
            font=("微软雅黑", 14, "bold")).pack(pady=15)
        
        # 滚动文本区域
        text_frame = Frame(win, bg="white")
        text_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        scrollbar = Scrollbar(text_frame)
        scrollbar.pack(side='right', fill='y')
        
        text = Text(text_frame, wrap='word', font=("微软雅黑", 10), bg="white",
                    relief="solid", bd=1, yscrollcommand=scrollbar.set)
        text.pack(fill='both', expand=True)
        scrollbar.config(command=text.yview)
        
        guide_content = """
    【软件简介】
    笔记本高清视频修复 2025 V7.0 是一款专业的视频后期处理工具，采用专业8步修复流程，支持GPU加速。

    【快速开始】
    1. 添加任务：点击"添加任务"按钮或直接拖拽视频文件到窗口
    2. 配置处理：在弹出的对话框中选择需要的处理选项
    3. 开始处理：点击"开始"按钮开始处理视频
    4. 查看结果：处理完成后可在原视频目录找到输出文件

    【处理功能说明】

    🔧 细节修复（专业8步流程）
    - 伪影移除 - 去除视频中的块状伪影和色带
    - 预锐化 - 边缘增强，自动回调避免过锐
    - 抗锯齿 - 平滑锯齿边缘
    - 去噪 - 智能降噪，保留细节
    - 人脸修复 - 优化人脸区域
    - 毛发保护 - 保留毛发细节
    - 最终锐化 - 轻微锐化提升清晰度
    - 颗粒添加 - 可选，增加胶片质感

    🎨 智能后期
    - 提亮/对比/鲜艳 - 基础调色
    - 冷白/压光 - 色温和高光调整
    - 锐化/质感 - 提升画面质感

    🎭 滤镜效果
    - 风景/老电影/电影/动漫 - 一键风格化

    🔬 高级后期
    - 自动白平衡/色阶 - 智能校色
    - 降噪/暗部/高光恢复 - 细节优化
    - 去雾 - 去除画面雾气

    【强度说明】
    - 轻度：适合画质较好的视频，轻微优化
    - 中度：适合大部分视频，平衡效果
    - 重度：适合画质较差的视频，强力修复

    【智能模式】
    开启后会自动分析画面质量，跳过不需要的处理步骤，提高效率。

    【资源占用】
    可通过右上角滑块调整处理时的系统资源占用比例（30%-100%）。

    【输出格式】
    输出使用H.264编码的MP4格式，兼容性好。

    【注意事项】
    - 处理前请确保FFmpeg已正确安装
    - 建议处理前先备份原视频
    - 大文件处理可能需要较长时间
    """
        
        text.insert('1.0', guide_content)
        text.config(state='disabled')
        
        # 关闭按钮
        Button(win, text="关闭", command=win.destroy, bg="#9E9E9E", fg="white",
            font=("微软雅黑", 10), relief="flat", width=12).pack(pady=15)

    def _show_about_window(self):
        """显示关于窗口"""
        win = Toplevel(self.root)
        win.title("关于")
        win.geometry("400x350")
        win.configure(bg="white")
        win.transient(self.root)
        win.resizable(False, False)
        
        # 居中显示
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_w = self.root.winfo_width()
        main_h = self.root.winfo_height()
        win_w, win_h = 400, 350
        x = main_x + (main_w - win_w) // 2
        y = main_y + (main_h - win_h) // 2
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")
        
        # 图标/标题
        Label(win, text="🎬", font=("", 50), bg="white").pack(pady=20)
        
        Label(win, text="笔记本高清视频修复 2025", bg="white", fg="#333",
            font=("微软雅黑", 16, "bold")).pack()
        
        Label(win, text="V7.0 后期处理专版", bg="white", fg="#666",
            font=("微软雅黑", 11)).pack(pady=5)
        
        # 分隔线
        Frame(win, bg="#e0e0e0", height=1).pack(fill='x', padx=40, pady=15)
        
        # 功能说明
        Label(win, text="专业8步修复流程，支持GPU加速", bg="white", fg="#333",
            font=("微软雅黑", 10)).pack()
        
        # GPU状态
        Label(win, text=f"当前设备: {self.gpu.get_status()}", bg="white", fg="#666",
            font=("微软雅黑", 9)).pack(pady=10)
        
        # 激活状态
        if self.activated:
            status_text = "✅ 已激活"
            status_color = "#4CAF50"
        else:
            status_text = "⚠️ 试用版"
            status_color = "#FF9800"
        
        Label(win, text=f"授权状态: {status_text}", bg="white", fg=status_color,
            font=("微软雅黑", 10)).pack()
        
        # 联系方式
        Label(win, text="客服邮箱: u788990@163.com", bg="white", fg="#999",
            font=("微软雅黑", 9)).pack(pady=15)
        
        # 关闭按钮
        Button(win, text="关闭", command=win.destroy, bg="#9E9E9E", fg="white",
            font=("微软雅黑", 10), relief="flat", width=12).pack(pady=10)

    def _check_ffmpeg_and_show(self, parent_win=None):
        """检测FFmpeg并更新显示"""
        PM.refresh()
        
        ffmpeg_path = PM.get_exe("ffmpeg")
        is_available = PM.is_exe_available("ffmpeg")
        
        if is_available:
            self.ffmpeg_status_label.config(text="✅ FFmpeg 已安装", fg="#4CAF50")
            self.ffmpeg_path_label.config(text=f"路径: {ffmpeg_path}")
            self.ffmpeg_download_btn.config(state=DISABLED, text="✓ 已安装")
        else:
            self.ffmpeg_status_label.config(text="❌ FFmpeg 未安装", fg="#F44336")
            self.ffmpeg_path_label.config(text="需要下载安装FFmpeg才能处理视频")
            self.ffmpeg_download_btn.config(state=NORMAL, text="📥 下载安装 FFmpeg")
        
        return is_available

    def _download_ffmpeg_ui(self, parent_win):
        """下载安装FFmpeg"""
        if PM.is_exe_available("ffmpeg"):
            messagebox.showinfo("提示", "FFmpeg 已经安装，无需重复下载")
            return
        
        # 显示进度区域
        self.ffmpeg_progress_frame.pack(fill='x', pady=10)
        self.ffmpeg_progress_bar['value'] = 0
        self.ffmpeg_progress_label.config(text="准备下载...")
        
        # 禁用按钮
        self.ffmpeg_download_btn.config(state=DISABLED, text="正在下载...")
        self.ffmpeg_check_btn.config(state=DISABLED)
        
        def update_progress(percent):
            self.ffmpeg_progress_bar['value'] = percent
            self.ffmpeg_progress_label.config(text=f"下载进度: {percent:.1f}%")
            self.root.update_idletasks()
        
        def download_thread():
            try:
                self.root.after(0, lambda: self.ffmpeg_progress_label.config(text="正在下载FFmpeg..."))
                
                success = self.downloader.download_component("ffmpeg", progress_cb=update_progress)
                
                if success:
                    PM.refresh()
                    self.root.after(0, lambda: self._on_ffmpeg_download_complete(True, parent_win))
                else:
                    self.root.after(0, lambda: self._on_ffmpeg_download_complete(False, parent_win))
            except Exception as e:
                self.root.after(0, lambda: self._on_ffmpeg_download_complete(False, parent_win, str(e)))
        
        threading.Thread(target=download_thread, daemon=True).start()

    def _on_ffmpeg_download_complete(self, success, parent_win, error_msg=None):
        """FFmpeg下载完成回调"""
        self.ffmpeg_check_btn.config(state=NORMAL)
        
        if success:
            self.ffmpeg_progress_label.config(text="✅ FFmpeg 安装成功!")
            self.ffmpeg_progress_bar['value'] = 100
            self.ffmpeg_status_label.config(text="✅ FFmpeg 已安装", fg="#4CAF50")
            self.ffmpeg_path_label.config(text=f"路径: {PM.get_exe('ffmpeg')}")
            self.ffmpeg_download_btn.config(text="✓ 已安装", state=DISABLED)
            messagebox.showinfo("成功", "FFmpeg 安装成功！现在可以开始处理视频了。")
        else:
            self.ffmpeg_progress_label.config(text=f"❌ 下载失败: {error_msg or '请检查网络'}")
            self.ffmpeg_download_btn.config(state=NORMAL, text="📥 重新下载")
            messagebox.showerror("下载失败", f"FFmpeg下载失败\n{error_msg or '请检查网络连接后重试'}")
        
        # 2秒后隐藏进度条
        self.root.after(2000, lambda: self.ffmpeg_progress_frame.pack_forget())

    def run(self):
        self.root.mainloop()

# ==================== 程序入口 ====================
if __name__ == "__main__":
    app = App()
    app.run()
