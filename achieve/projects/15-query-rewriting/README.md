# 15 - 查询改写与多路召回

本课在检索前增加一个查询改写步骤：

```text
用户问题
  ↓
DeepSeek 生成多个搜索表达
  ↓
每个表达分别进行混合检索
  ↓
RRF 融合多路结果
  ↓
把更完整的证据交给模型
```

## 安装依赖

```powershell
pip install -r .\projects\15-query-rewriting\requirements.txt
```

## 构建索引

```powershell
python .\projects\15-query-rewriting\main.py --rebuild
```

## 离线评测

```powershell
python .\projects\15-query-rewriting\main.py --eval
```

评测使用预先准备的查询变体，不调用 DeepSeek。

## 启动交互式 Agent

确保 `.env` 中已配置 DeepSeek：

```env
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_API_KEY=你的密钥
OPENAI_MODEL=deepseek-v4-flash
```

启动：

```powershell
python .\projects\15-query-rewriting\main.py
```

不使用查询改写进行对比：

```powershell
python .\projects\15-query-rewriting\main.py --no-rewrite
```

