# Architecture Map

## Junction-Based Architecture

The installer separates user data from ComfyUI core to allow clean `git pull` updates.

```mermaid
graph TD
    subgraph "Install Directory (user data persists)"
        M["models/"]
        O["output/"]
        I["input/"]
        U["user/"]
        S["scripts/"]
        L["UmeAiRT-Start-ComfyUI.bat"]
    end

    subgraph "ComfyUI/ (git repo, can be wiped)"
        CM["ComfyUI/models/"] -.->|junction| M
        CO["ComfyUI/output/"] -.->|junction| O
        CI["ComfyUI/input/"]  -.->|junction| I
        CU["ComfyUI/user/"]   -.->|junction| U
        CN["ComfyUI/custom_nodes/"]
        CX["ComfyUI/main.py"]
    end

    style M fill:#2d6a2e,stroke:#333
    style O fill:#2d6a2e,stroke:#333
    style I fill:#2d6a2e,stroke:#333
    style U fill:#2d6a2e,stroke:#333
```

## Configuration Data Flow

```mermaid
graph LR
    DJ["dependencies.json"] -->|Pydantic| DC["DependenciesConfig"]
    DC -->|repos| P2["phase2.py"]
    DC -->|pip_packages| P2
    DC -->|tools| P1["phase1.py"]
    DC -->|files| P2

    CNJ["custom_nodes.json"] -->|Pydantic| NM["NodeManifest"]
    NM -->|nodes| NO["nodes.py"]
    NO -->|install_node()| CN["custom_nodes/"]
    NO -->|update_node()| CN
```

## Logging Architecture

```mermaid
graph TD
    C["CLI (cli.py)"] -->|"--verbose flag"| SL["setup_logger()"]
    SL --> IL["InstallerLogger"]
    IL --> CON["Console Output"]
    IL --> FIL["Log File"]

    IL -->|"level 0 (step)"| CON
    IL -->|"level 1 (item)"| CON
    IL -->|"level 2 (sub)"| CON
    IL -->|"level 3 (info)"| VF{"verbose?"}
    VF -->|Yes| CON
    VF -->|No| SKIP["Hidden from console"]
    IL -->|"all levels"| FIL
```

## Custom Node Installation Flow

```mermaid
graph TD
    MF["custom_nodes.json"] --> LM["load_manifest()"]
    LM --> IA["install_all_nodes()"]
    IA --> IN["install_node()"]

    IN --> EX{"node_dir exists?"}
    EX -->|Yes| SK["Skip (already installed)"]
    EX -->|No| CL["git clone (3x retry, 300s timeout)"]
    CL --> R1{"Success?"}
    R1 -->|No, attempt 2+| SC["Shallow clone (--depth 1)"]
    SC --> R2{"Success?"}
    R2 -->|No, final| FAIL["Log failure"]
    R1 -->|Yes| REQ{"requirements.txt?"}
    R2 -->|Yes| REQ
    REQ -->|Yes| PIP["uv pip install / pip install"]
    REQ -->|No| DONE["Done"]
```

## Triton/SageAttention Compatibility

Version constraints based on PyTorch version (logic in `phase2.py`):

| PyTorch | triton-windows | Notes |
|---------|----------------|-------|
| 2.7.x | `==3.2.0` | Oldest supported |
| 2.8.x | `>=3.2.0,<3.4.0` | |
| 2.9.x | `>=3.3.0,<3.5.0` | |
| 2.10.x+ | `>=3.4.0` | Latest |

> Inspired by [DazzleML/comfyui-triton-and-sageattention-installer](https://github.com/DazzleML/comfyui-triton-and-sageattention-installer).
