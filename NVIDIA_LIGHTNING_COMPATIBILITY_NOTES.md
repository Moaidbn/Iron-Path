# ملاحظات توافق Nemotron 3.5 Lightning

## النتيجة الأساسية

المعرف `nvidia/nemotron-3.5-lightning:free` هو معرف **OpenRouter** لممره المجاني، وليس معرفًا صالحًا كما هو لنقطة NVIDIA Integrate. تستخدم OpenRouter نقطة `https://openrouter.ai/api/v1/chat/completions` ومفتاح OpenRouter، بينما تستخدم اللعبة حاليًا نقطة NVIDIA Integrate ومفتاح NVIDIA.[1] [2]

للاستخدام عبر NVIDIA Integrate، يشير نموذج NVIDIA الرسمي إلى المعرف:

```text
nvidia/nemotron-3.5-lightning-30b-a3b
```

## خصائص مؤثرة على اللعبة

| الخاصية | الأثر |
|---|---|
| 30B إجمالي / 3B فعّال | مرشح منطقي لزمن أسرع من نموذج 120B في الأدوار اليومية. |
| سياق حتى 1M token | أكبر بكثير من حاجة الوضعين `compact` و`full` الحاليين. |
| نطاق الاستخدام | موجه للمهام العميلية واتباع التعليمات والإخراج المنظم. |
| اللغة | صفحة NVIDIA المختصرة تسمي الإنجليزية والإسبانية والفرنسية والألمانية والإيطالية واليابانية؛ العربية ليست ضمن القائمة المسماة، لذلك يجب اعتماد اختبار العربية قبل استخدامه كنموذج افتراضي للعبة. |

## حدود تطبيق اللعبة الحالية

طبقة `nvidia_gm.py` تقيد القيم التي يرسلها ملف البيئة:

| المتغير | الحدود المقبولة في التطبيق | القيمة المقترحة اليومية |
|---|---:|---:|
| `NVIDIA_GM_TIMEOUT_SECONDS` | 5–120 ثانية | 30–60 ثانية |
| `NVIDIA_GM_MAX_TOKENS` | 160–1800 token | 900 token للوضع `compact` |

وبالتالي، القيمتان `3600` و`8900` لا تطبقان كما هما؛ ستُقصان داخليًا إلى 120 و1800، وهما غير مناسبتين لتجربة لعب سريعة على أي حال.

## المراجع

[1]: https://openrouter.ai/nvidia/nemotron-3.5-lightning:free "OpenRouter: NVIDIA Nemotron 3.5 Lightning (free)"
[2]: https://openrouter.ai/docs/quickstart "OpenRouter API Quickstart"
[3]: https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b "NVIDIA API Reference: Nemotron 3.5 Lightning 30B A3B"
