"""Tests for the GPU Scheduler module."""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock torch and pynvml before importing
sys.modules['torch'] = MagicMock()
sys.modules['pynvml'] = MagicMock()

from gpu_scheduler import GPUScheduler, read_gpu_stats, get_vram_usage


class TestReadGpuStats:
    @patch('gpu_scheduler.GPU_AVAILABLE', True)
    @patch('gpu_scheduler.pynvml')
    def test_returns_list_when_available(self, mock_pynvml):
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(
            used=4 * 1048576,  # 4MB
            total=48 * 1048576,  # 48MB
            free=44 * 1048576,  # 44MB
        )
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = MagicMock(gpu=50)
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 65
        mock_pynvml.nvmlDeviceGetName.return_value = b'RTX A6000'
        mock_pynvml.NVML_TEMPERATURE_GPU = 0

        stats = read_gpu_stats()
        assert isinstance(stats, list)
        assert len(stats) == 1
        assert stats[0]['gpu_id'] == 0
        assert stats[0]['name'] == 'RTX A6000'
        assert stats[0]['vram_used_mb'] == 4
        assert stats[0]['vram_total_mb'] == 48
        assert stats[0]['gpu_util_percent'] == 50
        assert stats[0]['temperature_c'] == 65

    @patch('gpu_scheduler.GPU_AVAILABLE', False)
    def test_returns_empty_when_unavailable(self):
        stats = read_gpu_stats()
        assert stats == []

    @patch('gpu_scheduler.GPU_AVAILABLE', True)
    @patch('gpu_scheduler.pynvml')
    def test_handles_multiple_gpus(self, mock_pynvml):
        mock_pynvml.nvmlDeviceGetCount.return_value = 2
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = MagicMock()
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(
            used=1048576, total=10485760, free=9437184
        )
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = MagicMock(gpu=30)
        mock_pynvml.nvmlDeviceGetTemperature.return_value = 55
        mock_pynvml.nvmlDeviceGetName.return_value = 'GPU'
        mock_pynvml.NVML_TEMPERATURE_GPU = 0

        stats = read_gpu_stats()
        assert len(stats) == 2

    @patch('gpu_scheduler.GPU_AVAILABLE', True)
    @patch('gpu_scheduler.pynvml')
    def test_handles_temp_error(self, mock_pynvml):
        mock_pynvml.nvmlDeviceGetCount.return_value = 1
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = MagicMock()
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(
            used=0, total=10485760, free=10485760
        )
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = MagicMock(gpu=0)
        mock_pynvml.nvmlDeviceGetTemperature.side_effect = Exception("not supported")
        mock_pynvml.nvmlDeviceGetName.return_value = 'GPU'
        mock_pynvml.NVML_TEMPERATURE_GPU = 0

        stats = read_gpu_stats()
        assert stats[0]['temperature_c'] is None


class TestGetVramUsage:
    @patch('gpu_scheduler.GPU_AVAILABLE', True)
    @patch('gpu_scheduler.pynvml')
    def test_returns_vram_info(self, mock_pynvml):
        mock_handle = MagicMock()
        mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle
        mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = MagicMock(
            used=20 * 1048576,
            total=48 * 1048576,
            free=28 * 1048576,
        )
        mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = MagicMock(gpu=42)

        usage = get_vram_usage()
        assert usage['total_mb'] == 48
        assert usage['used_mb'] == 20
        assert usage['free_mb'] == 28
        assert usage['utilization'] == 42

    @patch('gpu_scheduler.GPU_AVAILABLE', False)
    def test_returns_zeros_when_unavailable(self):
        usage = get_vram_usage()
        assert usage['total_mb'] == 0
        assert usage['used_mb'] == 0
        assert usage['free_mb'] == 0
        assert usage['utilization'] == 0

    @patch('gpu_scheduler.GPU_AVAILABLE', True)
    @patch('gpu_scheduler.pynvml')
    def test_handles_exception(self, mock_pynvml):
        mock_pynvml.nvmlDeviceGetHandleByIndex.side_effect = Exception("error")
        usage = get_vram_usage()
        assert usage['total_mb'] == 0


class TestGPUScheduler:
    def test_init_defaults(self):
        scheduler = GPUScheduler()
        assert scheduler.max_concurrent == 12  # Default from env or hardcoded
        assert scheduler.active_sessions == {}
        assert scheduler.cuda_streams == {}

    def test_init_custom(self):
        scheduler = GPUScheduler(max_concurrent=4)
        assert scheduler.max_concurrent == 4

    @patch('gpu_scheduler.GPU_AVAILABLE', False)
    def test_get_stats_basic(self):
        scheduler = GPUScheduler(max_concurrent=4)
        stats = scheduler.get_stats()
        assert stats['active_sessions'] == 0
        assert stats['max_concurrent'] == 4
        assert stats['slots_available'] == 4

    @pytest.mark.asyncio
    async def test_release_nonexistent_session(self):
        scheduler = GPUScheduler()
        # Should not raise
        await scheduler.release_slot("nonexistent_session")
        assert len(scheduler.active_sessions) == 0

    def test_get_stats_after_init(self):
        scheduler = GPUScheduler(max_concurrent=8)
        stats = scheduler.get_stats()
        assert stats['active_sessions'] == 0
        assert stats['max_concurrent'] == 8
        assert stats['slots_available'] == 8
