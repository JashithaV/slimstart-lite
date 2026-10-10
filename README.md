# SlimStart-Lite

A mini implementation inspired by *“Efficient Serverless Cold Start: Reducing Library Loading Overhead by Profile-guided Optimization.”* It uses workload profiling and AST-based lazy loading to reduce unnecessary library initialization in AWS Lambda.

**Workflow:**
```bash
python slimstart_lite.py profile
python slimstart_lite.py report
python slimstart_lite.py optimize

./build.sh app
./build.sh app_opt

./deploy.sh slim-baseline dist/app.zip YOUR_S3_BUCKET
./deploy.sh slim-optimized dist/app_opt.zip YOUR_S3_BUCKET

python benchmark.py slim-baseline 30
python benchmark.py slim-optimized 30
```

**Results:** In 30-run benchmarks, mean initialization time decreased from **3819 ms to 2258 ms (~40.9%)**, with reported memory usage decreasing from **184 MB to 122 MB**.

**Technologies:** Python, AST, AWS Lambda, Amazon S3, CloudWatch, Boto3.
