import asyncio
import edge_tts
import hashlib
import os
import json
import time

# 配置
AUDIO_DIR = "C:/Users/37810/urdu-learn-capacitor/www/audio"
VOICE = "ur-PK-UzmaNeural"  # 巴基斯坦乌尔都语女声
BATCH_SIZE = 50  # 每批处理数量，避免限流
BATCH_DELAY = 3  # 批次间隔秒数

# 读取文本列表
words = []
examples = []

with open(os.path.join(AUDIO_DIR, "audio_items.txt"), "r", encoding="utf-8") as f:
    section = None
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            if "Words" in line:
                section = "words"
            elif "Examples" in line:
                section = "examples"
            continue
        if section == "words":
            words.append(line)
        elif section == "examples":
            examples.append(line)

print(f"Words: {len(words)}, Examples: {len(examples)}, Total: {len(words) + len(examples)}")

# 生成所有任务列表
all_tasks = []

# 单词任务
def get_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]

for i, text in enumerate(words):
    h = get_hash(text)
    all_tasks.append({
        "id": f"w_{i}",
        "text": text,
        "file": os.path.join(AUDIO_DIR, f"w_{h}.mp3"),
        "type": "word"
    })

# 例句任务
for i, text in enumerate(examples):
    h = get_hash(text)
    all_tasks.append({
        "id": f"e_{i}",
        "text": text,
        "file": os.path.join(AUDIO_DIR, f"e_{h}.mp3"),
        "type": "example"
    })

print(f"Total tasks: {len(all_tasks)}")

# 检查已存在的文件
existing = 0
for task in all_tasks:
    if os.path.exists(task["file"]):
        existing += 1
print(f"Already existing: {existing}")

# 生成映射表
mapping = {}
for task in all_tasks:
    mapping[task["text"]] = os.path.basename(task["file"])

with open(os.path.join(AUDIO_DIR, "audio_map.json"), "w", encoding="utf-8") as f:
    json.dump(mapping, f, ensure_ascii=False, indent=2)
print(f"Mapping saved: {len(mapping)} entries")

# 批量生成音频
async def generate_batch(batch):
    semaphore = asyncio.Semaphore(3)  # 限制并发3个
    
    async def generate_one(task):
        async with semaphore:
            if os.path.exists(task["file"]):
                return {"status": "skipped", "task": task}
            try:
                communicate = edge_tts.Communicate(task["text"], VOICE)
                await communicate.save(task["file"])
                return {"status": "success", "task": task}
            except Exception as e:
                return {"status": "error", "task": task, "error": str(e)}
    
    results = await asyncio.gather(*[generate_one(t) for t in batch])
    return results

async def main():
    total = len(all_tasks)
    completed = 0
    success = 0
    skipped = 0
    errors = 0
    
    # 分批处理
    for i in range(0, total, BATCH_SIZE):
        batch = all_tasks[i:i+BATCH_SIZE]
        print(f"\nBatch {i//BATCH_SIZE + 1}/{(total-1)//BATCH_SIZE + 1} ({i+1}-{min(i+BATCH_SIZE, total)})")
        
        results = await generate_batch(batch)
        
        for r in results:
            completed += 1
            if r["status"] == "success":
                success += 1
            elif r["status"] == "skipped":
                skipped += 1
            else:
                errors += 1
                print(f"  ERROR: {r['task']['text'][:50]}... -> {r.get('error', 'unknown')}")
        
        print(f"  Progress: {completed}/{total} (success={success}, skipped={skipped}, errors={errors})")
        
        # 批次间隔，避免限流
        if i + BATCH_SIZE < total:
            print(f"  Waiting {BATCH_DELAY}s...")
            await asyncio.sleep(BATCH_DELAY)
    
    print(f"\n=== DONE ===")
    print(f"Total: {total}, Success: {success}, Skipped: {skipped}, Errors: {errors}")

asyncio.run(main())
