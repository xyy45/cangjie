# 安装、启动与部署诊断

当前交付工作面向macOS ARM64、CPython3.12.4、仓颉SDK1.0.5、stdx1.0.5.1及MacOSX15.4开发SDK。其他平台／组合未验收。本说明随源运行包提供；完整部署验收状态另见阶段报告，历史模型成功不能当作本次安装成功。

## 安装

在解压后的应用根目录执行。目录无需`.git`，不依赖开发者的PYTHONPATH或旧运行库。

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python scripts/install_runtime.py
python scripts/build_core.py
```

离线依赖材料与源运行包分开提供。解压依赖材料后，可将第三条替换为：

```sh
python -m pip --isolated --disable-pip-version-check install --no-index --find-links /你的依赖材料/wheels --only-binary=:all: --require-hashes --no-cache-dir -r /你的依赖材料/requirements-hashed.txt
python -m pip check
```

离线材料的40项版本须与应用的requirements.lock一致。SDK安装脚本校验固定归档SHA-256；网络不可用时，可将取得的同版本原始发行归档放入`.runtime/downloads/sdk.tar.gz`及`stdx.zip`，再执行同一脚本。不得把旧的已安装SDK树、已编译core或旧批准当作本次安装结果。

MacOSX15.4开发SDK必须由宿主开发环境提供，固定位置为`/Library/Developer/CommandLineTools/SDKs/MacOSX15.4.sdk`。应用安装脚本不安装系统开发工具，也不自动替换其他系统SDK。归档和实际核心构建信息保留于`.runtime`，core更换后旧批准不再代表当前组件。

## 自检与运行

无需模型请求的检查和本地演示：

```sh
python scripts/doctor.py --provider rule --port 8877
python -m nexus.demo.app --provider rule --port 8877
```

浏览器打开`http://127.0.0.1:8877/`。这是本机直接会话Demo入口，不需要工作台配对密钥。`nexus.web.app`是另外保留操作者授权的入口，不要把它的历史配对步骤用于Demo。

rule使用明确的确定性提供器，不能作为真实大模型修复效果。真实DeepSeek运行前，将`.env.example`复制为`.env`并在本机填写获准的HTTPS服务地址、模型标识及密钥；再执行：

```sh
python -m scripts.doctor --provider deepseek --port 8877
python -m nexus.demo.app --provider deepseek --port 8877
```

配置存在只说明本机字段已填写，不证明API连通。新任务发送源码／需求／公开测试前按界面核对授权，真实请求产生服务费用；不要通过重复点击补发结果不明的调用。此安装说明不会自动运行模型健康检查或付费评测。

自检默认输出schema1 JSON：退出0表示本次要求满足，1表示缺项／不匹配／无法确认，2表示命令参数无效。它核对锁定依赖、SDK／core、固定开发SDK、配置存在性及回环端口。端口通过仅表示检查时可绑定，不能预约端口；服务启动仍可能遇到竞争。缺少配置时请补本机配置，缺少SDK／core时执行安装／构建命令，不旁路检查。

## 诊断与程序包

先保存一份当前自检结果，然后生成诊断包：

```sh
python scripts/doctor.py --provider rule --port 8877 > selfcheck.json
python scripts/diagnostics.py --output ../cangsight-diagnostic.zip
python scripts/package_app.py --output ../cangsight-source.zip
python scripts/package_app.py --verify ../cangsight-source.zip
```

自检缺项时仍会输出JSON，命令退出1；可继续对这份报告生成诊断。诊断脚本仅读取应用根的`selfcheck.json`，选择允许字段，不重新探测环境；包中明确标记`SUPPLIED_SELF_CHECK_REPORT_NOT_REPROBED`，因此旧报告不能当作当前自检。诊断生成退出0表示材料创建成功，不表示报告所有检查通过。

诊断不复制原报告额外字段、`.env`、上传源码、SQLite、浏览器会话或模型调用原件。源程序包按`deployment-files.json`的固定范围生成，排除整个运行库、开发环境和旧历史审批。输出拒绝覆盖；失败临时`.part`保留用于核查，不能当作已完成程序包。校验清单用于检测材料不一致，不提供发布者签名或来源认证。

## 样例与证据

新安装保留登记的业务缺陷样例和修复入口，初始为SAMPLE；不带旧会话、审批或模型调用ZIP。开发目录中完整的历史回放集合仍可使用，并继续显示其历史来源；只有部分历史文件时会报错，不能把损坏的回放降级成正常样例。源码分析的本地样例与真实MCP结果按原来源显示，不能把缓存／夹具当作当前分析质量。

本地运行数据固定放在应用目录`.runtime/demo-workbench`，当前CLI只有provider和port选项。不要共享这个目录、会话签名密钥或`.env`，不要将测试工作放入已有主站数据。新交付测试使用新解压目录和独立端口。

正常停止自己的服务后再重启。持有OS文件锁的控制器才可写；第二实例不能取得写权。重启保留任务原件和本机会话，未开始任务或在途任务会保守停止／标记待核实，不自动续跑模型请求、补丁或导出。审阅和导出绑定当前源码、验证、组件、会话及有效期，不能恢复旧批准来跳过核对。

## 功能核对

准备上传→选择函数及编辑范围→填写／导入预期行为和测试→核对规则草案→确认冻结→修复迭代→独立编译／测试／规则验证→人工审阅→导出并下载。FAIL、UNKNOWN和未运行保持区分；有限测试通过不等于任意输入正确。外部分析／模型未配置时保留真实受阻状态，不生成虚构成功。完整版本与本次实际命令、退出状态和下载摘要应随复现记录保存。
