# SlimStart-Lite
Mini implementation of "Efficient Serverless Cold Start: Reducing Library Loading Overhead by Profile-guided Optimization".

    python slimstart_lite.py profile            # sample a simulated workload (90/8/2 mix) -> profile.json
    python slimstart_lite.py report             # init time vs utilization per library
    python slimstart_lite.py optimize           # AST rewrite: flagged global imports -> deferred imports (app_opt/)

AWS (free tier): see build.sh, deploy.sh, benchmark.py
    ./build.sh app && ./build.sh app_opt
    ./deploy.sh slim-baseline dist/app.zip  <bucket>
    ./deploy.sh slim-optimized dist/app_opt.zip <bucket>
    python benchmark.py slim-baseline 30 ; python benchmark.py slim-optimized 30
