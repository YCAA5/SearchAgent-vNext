# Search Agent vNext

A local Windows semantic document finder using Qwen3-Embedding-0.6B. Describe remembered contents; exact wording is not required.

Extract the entire Windows ZIP and open SearchAgent.exe. Add locations, click **Prepare / update search**, wait for preparation, then search. The English/Türkçe menu switches UI language without translating document contents. Light/dark themes, three icon sizes, cards/list layouts and PDF/image previews are supported.

Multiple local disks, removable disks and UNC/mapped shares can be selected. Disconnected locations retain previously indexed content. Removed locations are pruned on update. Network failure behavior is covered by simulations; a real NAS/SMB endpoint was not tested.

Search snapshots and repeated query vectors are cached. Changed documents are embedded in bounded cross-document batches. Preparing an update preserves the last ready semantic index and supports resuming committed work.

The executable uses a separate per-user %LOCALAPPDATA%/SearchAgent-vNext profile. An existing SearchAgent profile is not overwritten. Shared computer users should use separate Windows accounts; this is not a centralized multi-user search server.

The complete program guide and engineering system sizing recommendations are in [PROGRAM.md](PROGRAM.md), in Turkish. Suggested starting capacity: Windows x64, 4 CPU cores, 8 GB RAM and 5 GB free disk plus index growth; recommended: Windows 11 x64, 6–8 cores, 16 GB RAM, local SSD and 10 GB+ free space. A compatible GPU is optional; 4 GB+ VRAM is a practical recommendation. These are sizing targets, not benchmarks on all such hardware.

See [changes](CHANGELOG.md), [build](docs/BUILD.md) and [distribution](docs/DISTRIBUTION.md). requirements-lock.txt records the tested Python environment. Source exports exclude private profiles, documents, indexes, secrets, logs, virtual environments and model weights. No GitHub publication is performed automatically.
