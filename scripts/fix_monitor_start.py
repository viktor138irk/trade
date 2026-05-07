from pathlib import Path

path = Path('app/main.py')
text = path.read_text()
old = """def ensure_monitor_running() -> None:\n    global monitor_task\n    if monitor_task is None or monitor_task.done():\n        monitor_task = asyncio.create_task(monitor.loop(SessionLocal, interval_seconds=10))\n"""
new = """def ensure_monitor_running() -> None:\n    global monitor_task\n\n    if monitor_task is not None and not monitor_task.done() and not monitor.running:\n        monitor_task.cancel()\n        monitor_task = None\n\n    if monitor_task is None or monitor_task.done():\n        monitor_task = asyncio.create_task(monitor.loop(SessionLocal, interval_seconds=10))\n"""
if old not in text:
    print('ensure_monitor_running already patched or function shape differs')
else:
    path.write_text(text.replace(old, new))
    print('monitor start/restart patch applied')
