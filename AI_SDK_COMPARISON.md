# AI SDK Integration Approaches

This document compares different approaches for integrating AI models with the Blender MCP server.

## 🚫 **Previous Approach (NOT Recommended)**

**Raw HTTP Calls with httpx.AsyncClient**
```python
# ❌ DON'T DO THIS
async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "claude-3-5-sonnet-20241022", "messages": [...]}
    )
```

**Problems:**
- ❌ Manual error handling
- ❌ No automatic retries
- ❌ Missing rate limiting
- ❌ No streaming support
- ❌ Authentication complexity
- ❌ Response parsing overhead

## ✅ **Recommended Approaches**

### **1. Official SDKs (BEST)**

**Anthropic SDK:**
```python
import anthropic

client = anthropic.AsyncAnthropic(api_key=api_key)
response = await client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=4000,
    messages=[{"role": "user", "content": message}]
)
```

**OpenAI SDK:**
```python
import openai

client = openai.AsyncOpenAI(api_key=api_key)
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": message}],
    max_tokens=4000
)
```

**Benefits:**
- ✅ Robust error handling and retries
- ✅ Automatic rate limiting
- ✅ Streaming support
- ✅ Type safety with proper models
- ✅ Regular updates and maintenance
- ✅ Built-in authentication handling

### **2. LiteLLM (Multi-Provider)**

**Unified Interface for Multiple Providers:**
```python
import litellm

# Works with 100+ providers using same interface
response = await litellm.acompletion(
    model="claude-3-5-sonnet-20241022",  # or "gpt-4o", "gemini-pro", etc.
    messages=[{"role": "user", "content": message}],
    max_tokens=4000
)
```

**Benefits:**
- ✅ Single interface for all providers
- ✅ Easy provider switching
- ✅ Consistent error handling
- ✅ Cost tracking and logging
- ✅ Fallback provider support

### **3. LangChain (Full Framework)**

**For Complex AI Applications:**
```python
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage

llm = ChatAnthropic(model_name="claude-3-5-sonnet-20241022")
response = await llm.ainvoke([HumanMessage(content=message)])
```

**Benefits:**
- ✅ Rich ecosystem of tools
- ✅ Built-in memory and agents
- ✅ Vector store integrations
- ✅ Complex workflow orchestration

## 📊 **Comparison Matrix**

| Feature | Raw HTTP | Official SDKs | LiteLLM | LangChain |
|---------|----------|---------------|---------|-----------|
| **Simplicity** | ❌ Low | ✅ High | ✅ High | ⚠️ Medium |
| **Error Handling** | ❌ Manual | ✅ Built-in | ✅ Built-in | ✅ Built-in |
| **Multi-Provider** | ❌ No | ❌ No | ✅ Yes | ✅ Yes |
| **Type Safety** | ❌ No | ✅ Yes | ⚠️ Partial | ✅ Yes |
| **Maintenance** | ❌ You | ✅ Official | ✅ Community | ✅ Community |
| **Learning Curve** | ⚠️ Medium | ✅ Low | ✅ Low | ❌ High |
| **Performance** | ⚠️ Manual | ✅ Optimized | ✅ Optimized | ⚠️ Overhead |

## 🚀 **Implementation Examples**

### **Setup Dependencies**

```bash
# Install all approaches
uv add anthropic openai litellm langchain langchain-anthropic langchain-openai
```

### **Environment Variables**

```bash
# .env file
ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-openai-key-here
AI_PROVIDER=claude  # or openai
AI_APPROACH=official  # official, litellm, langchain
```

### **Usage in Blender MCP Client**

```python
# Test different approaches
./scripts/test_blender.sh compare        # Compare all approaches
./scripts/test_blender.sh ai-improved    # Use improved client

# Environment variables
AI_APPROACH=official ./scripts/test_blender.sh ai-improved
AI_APPROACH=litellm ./scripts/test_blender.sh ai-improved
AI_PROVIDER=openai ./scripts/test_blender.sh ai-improved
```

## 🎯 **Recommendations**

### **For Production Applications:**
1. **Use Official SDKs** (`anthropic`, `openai`) for single-provider applications
2. **Use LiteLLM** for multi-provider flexibility
3. **Use LangChain** only if you need complex AI workflows

### **For Development/Prototyping:**
1. Start with **Official SDKs** for simplicity
2. Switch to **LiteLLM** when you need provider flexibility
3. Avoid raw HTTP calls unless absolutely necessary

### **For Our Blender MCP Integration:**
- **Current Implementation**: Official SDKs (anthropic, openai)
- **Future Enhancement**: LiteLLM for provider flexibility
- **Advanced Features**: Consider LangChain for AI agents that can perform complex Blender tasks

## 🔧 **Migration Guide**

### **From Raw HTTP to Official SDK:**

**Before (❌):**
```python
async with httpx.AsyncClient() as client:
    response = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": "claude-3-5-sonnet-20241022", "messages": messages}
    )
    result = response.json()
```

**After (✅):**
```python
client = anthropic.AsyncAnthropic(api_key=api_key)
response = await client.messages.create(
    model="claude-3-5-sonnet-20241022",
    messages=messages,
    max_tokens=4000
)
result = response.content[0].text
```

### **Benefits Gained:**
- 🚀 **60% less code**
- 🛡️ **Built-in error handling**
- ⚡ **Automatic retries**
- 🔄 **Connection pooling**
- 📊 **Better debugging** 