#!/usr/bin/env python3
"""
可靠的 CSV 追加写入工具（面向长时间运行的日志场景）。

设计目标：
1) 轻量检测文件是否被“原子保存/替换”(inode 变化)；变化后自动 reopen 并继续追加写入。
2) 遇到 OSError（例如磁盘抖动、临时不可写）不永久禁用日志，而是退避重试 reopen。
3) 控制 flush 频率，避免每行 flush 带来的性能开销，同时尽量降低数据丢失窗口。
"""

from __future__ import annotations

import csv
import os
import time
from typing import Any, Iterable, Optional, Sequence, TextIO


class ResilientCsvWriter:
    def __init__(
        self,
        path: str,
        header: Sequence[str],
        *,
        flush_every: int = 10,
        flush_interval_s: float = 1.0,
        inode_check_every: int = 50,
        inode_check_interval_s: float = 1.0,
        retry_base_interval_s: float = 5.0,
        retry_max_interval_s: float = 60.0,
        encoding: str = "utf-8",
        verbose: bool = False,
        label: str = "csv",
    ) -> None:
        self._path = path
        self._header = list(header)
        self._flush_every = max(1, int(flush_every))
        self._flush_interval_s = max(0.0, float(flush_interval_s))
        self._inode_check_every = max(1, int(inode_check_every))
        self._inode_check_interval_s = max(0.0, float(inode_check_interval_s))
        self._retry_base_interval_s = max(0.1, float(retry_base_interval_s))
        self._retry_max_interval_s = max(self._retry_base_interval_s, float(retry_max_interval_s))
        self._encoding = encoding
        self._verbose = bool(verbose)
        self._label = label

        self._file: Optional[TextIO] = None
        self._writer: Optional[csv.writer] = None

        self._write_count = 0
        self._writes_since_flush = 0
        self._writes_since_inode_check = 0
        self._last_flush_at: float = 0.0
        self._last_inode_check_at: float = 0.0

        self._next_retry_at: float = 0.0
        self._retry_interval_s: float = self._retry_base_interval_s

    @property
    def path(self) -> str:
        return self._path

    def ensure_open(self) -> bool:
        """尝试立即打开文件；失败则安排退避重试。"""
        return self._ensure_open(time.time())

    def write_row(self, row: Sequence[Any]) -> bool:
        now = time.time()
        if not self._ensure_open(now):
            return False

        if not self._ensure_inode_consistent(now):
            return False

        try:
            if self._writer is None:
                return False
            self._writer.writerow(row)
            self._write_count += 1
            self._writes_since_flush += 1
        except (OSError, ValueError) as exc:
            self._handle_io_error(exc, context="write")
            return False

        self._maybe_flush(now)
        return True

    def write_rows(self, rows: Iterable[Sequence[Any]]) -> int:
        written = 0
        for row in rows:
            if self.write_row(row):
                written += 1
        return written

    def flush(self) -> None:
        if self._file is None:
            return
        try:
            self._file.flush()
            self._writes_since_flush = 0
            self._last_flush_at = time.time()
        except (OSError, ValueError) as exc:
            self._handle_io_error(exc, context="flush")

    def close(self) -> None:
        if self._file is None:
            return
        try:
            try:
                self._file.flush()
            except Exception:
                pass
            self._file.close()
        except Exception:
            pass
        finally:
            self._file = None
            self._writer = None

    def _ensure_open(self, now: float) -> bool:
        if self._file is not None and self._writer is not None:
            return True

        if now < self._next_retry_at:
            return False

        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            file_handle = open(self._path, "a", newline="", encoding=self._encoding)
            writer = csv.writer(file_handle)
            # 新文件或被清空后重新创建时写入表头
            if file_handle.tell() == 0:
                writer.writerow(self._header)
                file_handle.flush()
            self._file = file_handle
            self._writer = writer
            self._write_count = 0
            self._writes_since_flush = 0
            self._writes_since_inode_check = 0
            self._last_flush_at = now
            self._last_inode_check_at = now
            self._retry_interval_s = self._retry_base_interval_s
            return True
        except (OSError, ValueError) as exc:
            self._handle_io_error(exc, context="open")
            return False

    def _ensure_inode_consistent(self, now: float) -> bool:
        if self._file is None:
            return False

        self._writes_since_inode_check += 1
        should_check = self._writes_since_inode_check >= self._inode_check_every
        if not should_check and self._inode_check_interval_s > 0:
            should_check = (now - self._last_inode_check_at) >= self._inode_check_interval_s
        if not should_check:
            return True

        self._writes_since_inode_check = 0
        self._last_inode_check_at = now

        try:
            fd_inode = os.fstat(self._file.fileno()).st_ino
        except Exception:
            fd_inode = None

        try:
            path_inode = os.stat(self._path).st_ino
        except Exception:
            path_inode = None

        if fd_inode is None or path_inode is None or fd_inode != path_inode:
            if self._verbose:
                print(f"[{self._label}] Detected inode change for {self._path}, reopening log file...")
            self.close()
            return self._ensure_open(now)

        return True

    def _maybe_flush(self, now: float) -> None:
        if self._file is None:
            return

        if self._writes_since_flush >= self._flush_every:
            self.flush()
            return

        if self._flush_interval_s > 0 and (now - self._last_flush_at) >= self._flush_interval_s:
            self.flush()

    def _handle_io_error(self, exc: Exception, *, context: str) -> None:
        if self._verbose:
            print(f"[{self._label}] CSV {context} error on {self._path}: {exc}. Will retry...")

        self.close()

        now = time.time()
        self._next_retry_at = now + self._retry_interval_s
        self._retry_interval_s = min(self._retry_max_interval_s, self._retry_interval_s * 2)

