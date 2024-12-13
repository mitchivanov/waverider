import os
import asyncio
import aiofiles
import datetime

class AsyncLogger:
    def __init__(self, bot_id, max_queue_size=1000):
        # Создаем пути для логов конкретного бота
        self.info_filename = f'logs/bot_{bot_id}/trades.log'
        self.debug_filename = f'logs/bot_{bot_id}/debug.log'
        
        # Создаем отдельные очереди для каждого уровня логирования
        self.info_queue = asyncio.Queue(maxsize=max_queue_size)
        self.debug_queue = asyncio.Queue(maxsize=max_queue_size)
        self.running = True
        
        # Создаем директорию для логов конкретного бота
        os.makedirs(os.path.dirname(self.info_filename), exist_ok=True)
        
        # Start the logging processes
        asyncio.create_task(self._process_logs(self.info_queue, self.info_filename))
        asyncio.create_task(self._process_logs(self.debug_queue, self.debug_filename))

    async def _write_immediately(self, message, filename):
        """Immediate writing to the specified log file"""
        try:
            async with aiofiles.open(filename, mode='a') as f:
                await f.write(message)
        except Exception as e:
            print(f"Critical error writing to log: {e}")
            
    async def fatal(self, message):
        """logging and immediate exit"""
        formatted_message = f"[{datetime.datetime.now().isoformat()}] [FATAL] {message}\n"
        await self._write_immediately(formatted_message, self.debug_filename)
        os._exit(1)  # Immediate exit
        
    async def panic(self, message):
        """logging and raising panic"""
        formatted_message = f"[{datetime.datetime.now().isoformat()}] [PANIC] {message}\n"
        await self._write_immediately(formatted_message, self.debug_filename)
        raise RuntimeError(f"Panic: {message}")
        
    async def log(self, message):
        """logging an info message"""
        await self.info_queue.put(f"[{datetime.datetime.now().isoformat()}] [INFO] {message}\n")
        
    async def debug(self, message):
        """logging a debug message"""
        await self.debug_queue.put(f"[{datetime.datetime.now().isoformat()}] [DEBUG] {message}\n")
        
    async def _process_logs(self, queue, filename):
        """Processes the log queue and writes messages to the specified file"""
        while self.running:
            try:
                # Collect all available logs
                messages = []
                messages.append(await queue.get())
                
                # Check if there are any more logs in the queue
                while not queue.empty() and len(messages) < 100:
                    try:
                        messages.append(queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break
                
                # Write all collected logs at once
                async with aiofiles.open(filename, mode='a') as f:
                    await f.writelines(messages)
                    
            except Exception as e:
                print(f"Error writing to log file {filename}: {e}")
                await asyncio.sleep(1)
                
    async def close(self):
        """Closes the logger"""
        self.running = False
        # Wait for the remaining logs to be processed
        while not self.info_queue.empty() or not self.debug_queue.empty():
            await asyncio.sleep(0.1)

    async def error(self, message):
        """logging an error message"""
        formatted_message = f"[{datetime.datetime.now().isoformat()}] [ERROR] {message}\n"
        await self._write_immediately(formatted_message, self.debug_filename)