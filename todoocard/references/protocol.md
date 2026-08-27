# TodooCard Android transport

## Android Minis bridge

Android Minis 公开 `android-open`，但没有通用 BLE 或定位 CLI。本技能使用同机
companion：

1. Python 在 `127.0.0.1` 随机端口启动一次性 HTTP 服务。
2. `android-open` 打开
   `todoocard-minis://bridge/run?port=<port>&token=<48-hex>`。
3. companion 以 token 获取 JSON 请求，并用已信任的 256-bit `companion_key`
   做常量时间比较；首次连接需要用户在 companion UI 中确认信任。
   `send` 模式再获取经过校验的 payload。
4. `send` 期间 companion 每 5% 将带相同 `request_id` 的进度 JSON POST 到
   `/progress`，Minis 用它刷新活动时间并显示进度。
5. companion 完成 `scan`、`pair`、`probe`、`send` 或 `location`，将带相同
   `request_id` 的 JSON POST 回 localhost `/result`。
6. Python 验证 token 路径、request_id、mode 和 `ok` 后结束服务。

服务只绑定 loopback，不接受超过 1 MB 的结果。companion 不开放 socket、不
读取 Minis 文件系统，也不申请存储权限。

## Secure advertisement and pairing

当前安全 T3 广播 manufacturer `0x5053`、screen type `0x134C`。firmware
`0x8C+` 且 flag `0x01` 表示加密 GATT；flag `0x02` 表示实体配对窗口开启。

- `pair` 只在目标精确 MAC 且配对窗口开启时创建 Android system bond。
- bond 完成后必须成功读取加密 `180F/2A19` Battery Level。
- `probe` / `send` 从 Android bonded devices 按保存的精确 MAC 直接连接，不依赖
  厂商广播；连接后仍必须读取加密 `180F/2A19`，不能把“已保存 MAC”本身当作验证。
- 广播路径中的 `probe` / `send` 在配对窗口开启时拒绝执行。

## Image GATT

| UUID | Role |
|---|---|
| `FEF0` / `FDF0` | image service |
| `FEF1` / `FDF1` | control write + notify |
| `FEF2` / `FDF2` | indexed data write |

| Command | Meaning |
|---|---|
| `01` | request block size; typical response `01 F4 00`, payload 240 bytes |
| `02` | `02` + payload length u32le + flag `01` |
| `03` | start full-frame transfer |
| `05` | next requested block / flow-control acknowledgement; status `08` is final refresh acknowledgement |

Data packet: `[block index u32le][payload <= 240 bytes]`.

Android companion 连接后请求 `CONNECTION_PRIORITY_HIGH` 和至少 247 字节 MTU。
数据特征同时支持两种写法时优先 `WRITE_TYPE_DEFAULT`，每块收到 Android GATT
写确认后再推进，并对单块确认设置 10 秒看门狗。只有特征不支持确认写时才使用
12 ms 节奏的 `WRITE_NO_RESPONSE`，在 Android GATT 队列忙时退避重试。

## Image pipeline

1. cover-resize to 528x792
2. six-color Floyd-Steinberg palette mapping
3. configured safe mount orientation
4. nibble packing (209088 raw bytes)
5. SE0368 controller transform
6. QuickLZ stored framing: `00 00 00 00`, then repeated `74 43 40` + 64 bytes

Any GATT write failure, disconnect, invalid acknowledgement, or final timeout aborts the
operation. Never reconnect and resume from a non-zero block.

A non-zero block returned by the first `05` response can be stale state from an earlier
aborted session. Before any data write, the companion may ignore that offset and overwrite
the complete frame sequentially from block zero. During streaming, `05` normally returns
the same index as the sender's next unsent block; that is sequential flow control, not a
resume request. A lower index would require retransmitting old data and a higher index would
skip unsent data, so either mismatch aborts the operation and requires a new full-frame
transfer.
