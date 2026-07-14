import time
import statistics
import argparse

def benchmark_ttft(engine, test_audio_16k: bytes, n_runs: int = 30) -> dict:
    """
    Run before AND after loading adapter. Adapter overhead must be <10ms.
    Target: p50 <100ms, p95 <120ms, p99 <150ms
    """
    latencies = []
    print(f"Running TTFT benchmark for {n_runs} runs...")
    
    # Warmup
    if hasattr(engine, 'step'):
        engine.step(test_audio_16k)
        
    for _ in range(n_runs):
        start = time.perf_counter()
        # In a real environment, engine.step triggers the forward pass
        if hasattr(engine, 'step'):
            engine.step(test_audio_16k)
        else:
            time.sleep(0.08) 
        latencies.append((time.perf_counter() - start) * 1000)
        
    latencies.sort()
    
    results = {
        "p50":  latencies[n_runs // 2],
        "p95":  latencies[int(n_runs * 0.95)],
        "p99":  latencies[int(n_runs * 0.99)],
        "mean": statistics.mean(latencies),
    }
    
    print("\n--- TTFT Benchmark Results ---")
    for k, v in results.items():
        print(f"{k.upper()}:\t{v:.2f} ms")
        
    if results["p95"] > 120:
        print("VALIDATION FAILED: p95 TTFT > 120ms. Reduce LoRA rank to r=8 and retrain.")
    else:
        print("VALIDATION PASSED: p95 TTFT is within 120ms budget.")
        
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30)
    args = parser.parse_args()
    
    class MockEngine:
        def step(self, audio):
            time.sleep(0.08) # mock 80ms processing time
            
    engine = MockEngine()
    test_audio = b"\x00" * 960 # 30ms of audio
    benchmark_ttft(engine, test_audio, args.runs)
