#!/usr/bin/env python3
"""
Log cleanup script for AZIZA services.
Removes old log files and manages disk usage.

Usage:
    python3 cleanup_logs.py [--max-age-days 30] [--max-size-gb 5] [--dry-run]
"""

import os
import sys
import glob
import argparse
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = "/root/aziza-build/logs"
ARCHIVE_DIR = "/root/aziza-build/logs/archive"


def parse_log_date(filename: str) -> datetime | None:
    """Extract date from log filename (e.g., api-gateway-out.log.2026-07-11_00-00-00)."""
    # Look for date pattern in filename
    import re
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d')
        except ValueError:
            pass
    return None


def get_file_age_days(filepath: str) -> float:
    """Get file age in days."""
    stat = os.stat(filepath)
    age_seconds = datetime.now().timestamp() - stat.st_mtime
    return age_seconds / 86400


def cleanup_old_logs(max_age_days: int = 30, dry_run: bool = False):
    """Remove log files older than max_age_days."""
    removed = 0
    freed_bytes = 0

    for log_file in glob.glob(os.path.join(LOG_DIR, "*.log*")):
        if os.path.isdir(log_file):
            continue

        age_days = get_file_age_days(log_file)
        if age_days > max_age_days:
            size = os.path.getsize(log_file)
            if dry_run:
                print(f"  [DRY RUN] Would remove: {os.path.basename(log_file)} ({age_days:.0f} days old, {size / 1024 / 1024:.1f}MB)")
            else:
                os.remove(log_file)
                print(f"  Removed: {os.path.basename(log_file)} ({age_days:.0f} days old, {size / 1024 / 1024:.1f}MB)")
            removed += 1
            freed_bytes += size

    return removed, freed_bytes


def cleanup_by_total_size(max_size_gb: float = 5, dry_run: bool = False):
    """Remove oldest log files if total exceeds max_size_gb."""
    log_files = []
    total_size = 0

    for f in glob.glob(os.path.join(LOG_DIR, "*.log*")):
        if os.path.isdir(f):
            continue
        size = os.path.getsize(f)
        total_size += size
        log_files.append((f, size, os.path.getmtime(f)))

    max_bytes = max_size_gb * 1024 * 1024 * 1024
    if total_size <= max_bytes:
        print(f"  Total log size: {total_size / 1024 / 1024 / 1024:.2f}GB (under {max_size_gb}GB limit)")
        return 0, 0

    # Sort by modification time (oldest first)
    log_files.sort(key=lambda x: x[2])

    removed = 0
    freed_bytes = 0

    for filepath, size, mtime in log_files:
        if total_size <= max_bytes:
            break
        if dry_run:
            print(f"  [DRY RUN] Would remove: {os.path.basename(filepath)} ({size / 1024 / 1024:.1f}MB)")
        else:
            os.remove(filepath)
            print(f"  Removed: {os.path.basename(filepath)} ({size / 1024 / 1024:.1f}MB)")
        total_size -= size
        freed_bytes += size
        removed += 1

    return removed, freed_bytes


def compress_old_logs(max_age_days: int = 7, dry_run: bool = False):
    """Gzip log files older than max_age_days."""
    compressed = 0

    for log_file in glob.glob(os.path.join(LOG_DIR, "*.log")):
        if os.path.isdir(log_file):
            continue

        age_days = get_file_age_days(log_file)
        if age_days > max_age_days and not log_file.endswith('.gz'):
            gz_file = log_file + '.gz'
            if dry_run:
                print(f"  [DRY RUN] Would compress: {os.path.basename(log_file)}")
            else:
                with open(log_file, 'rb') as f_in:
                    with gzip.open(gz_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                os.remove(log_file)
                print(f"  Compressed: {os.path.basename(log_file)}")
            compressed += 1

    return compressed


def get_log_stats():
    """Get statistics about log files."""
    stats = {
        'total_files': 0,
        'total_size_bytes': 0,
        'by_service': {},
        'oldest': None,
        'newest': None,
    }

    for f in glob.glob(os.path.join(LOG_DIR, "*.log*")):
        if os.path.isdir(f):
            continue

        size = os.path.getsize(f)
        mtime = os.path.getmtime(f)
        name = os.path.basename(f)

        stats['total_files'] += 1
        stats['total_size_bytes'] += size

        # Extract service name
        service = name.split('-')[0] if '-' in name else 'other'
        if service not in stats['by_service']:
            stats['by_service'][service] = {'count': 0, 'size_bytes': 0}
        stats['by_service'][service]['count'] += 1
        stats['by_service'][service]['size_bytes'] += size

        if stats['oldest'] is None or mtime < stats['oldest']:
            stats['oldest'] = mtime
        if stats['newest'] is None or mtime > stats['newest']:
            stats['newest'] = mtime

    return stats


def main():
    parser = argparse.ArgumentParser(description='AZIZA Log Cleanup')
    parser.add_argument('--max-age-days', type=int, default=30, help='Max age in days for log files')
    parser.add_argument('--max-size-gb', type=float, default=5, help='Max total log size in GB')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    parser.add_argument('--compress', action='store_true', help='Compress old logs')
    parser.add_argument('--stats', action='store_true', help='Show log statistics')
    args = parser.parse_args()

    print(f"AZIZA Log Cleanup - {datetime.now().isoformat()}")
    print(f"Log directory: {LOG_DIR}")
    print()

    if args.stats:
        stats = get_log_stats()
        print(f"Total files: {stats['total_files']}")
        print(f"Total size: {stats['total_size_bytes'] / 1024 / 1024 / 1024:.2f}GB")
        print(f"\nBy service:")
        for service, data in sorted(stats['by_service'].items()):
            print(f"  {service}: {data['count']} files, {data['size_bytes'] / 1024 / 1024:.1f}MB")
        return

    # Compress old logs first
    if args.compress:
        print("Compressing old logs...")
        compressed = compress_old_logs(max_age_days=7, dry_run=args.dry_run)
        print(f"  Compressed {compressed} files\n")

    # Remove by age
    print(f"Removing logs older than {args.max_age_days} days...")
    removed_age, freed_age = cleanup_old_logs(args.max_age_days, args.dry_run)
    print(f"  Removed {removed_age} files, freed {freed_age / 1024 / 1024:.1f}MB\n")

    # Remove by total size
    print(f"Enforcing {args.max_size_gb}GB total size limit...")
    removed_size, freed_size = cleanup_by_total_size(args.max_size_gb, args.dry_run)
    print(f"  Removed {removed_size} files, freed {freed_size / 1024 / 1024:.1f}MB\n")

    # Final stats
    stats = get_log_stats()
    print(f"Final state: {stats['total_files']} files, {stats['total_size_bytes'] / 1024 / 1024 / 1024:.2f}GB total")


if __name__ == '__main__':
    main()
