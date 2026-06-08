# container-profiler (CASY)

CASY (**C**PU **C**ache **A**llocation **SY**stem) is a smart CPU cache allocation system for serverless functions that leverages Intel CAT technology. It uses **KNN** to build a cache usage profile for functions and uses this profile to predict the cache requirements based on the function's input data size.

Please check out CCGRID'22 [paper](https://ieeexplore.ieee.org/document/9825963) for more details.

## Reference

```bibtex
@INPROCEEDINGS{9825963,
  author={Jeatsa, Armel and Teabe, Boris and Hagimont, Daniel},
  booktitle={2022 22nd IEEE International Symposium on Cluster, Cloud and Internet Computing (CCGrid)}, 
  title={CASY: A CPU Cache Allocation System for FaaS Platform}, 
  year={2022},
  volume={},
  number={},
  pages={494-503},
  keywords={Runtime;Program processors;FAA;Pricing;Predictive models;Prediction algorithms;Software;FaaS;CPU Cache;Allocation},
  doi={10.1109/CCGrid54584.2022.00059}
}
```
