modules = [
    "streamlit",
    "numpy",
    "pyarrow",
    "yaml",
]

for m in modules:
    try:
        __import__(m)
        print(f"✅ {m} OK")
    except Exception as e:
        print(f"❌ {m} FAIL:", e)