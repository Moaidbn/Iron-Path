# NVIDIA Model Performance Notes

تمت مراجعة صفحات NVIDIA الرسمية في 13 أغسطس 2026.

## المصادر

1. [NVIDIA Nemotron 3 Super 120B A12B](https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b)
2. [NVIDIA Models Catalog](https://build.nvidia.com/models)
3. [NVIDIA AI Models](https://developer.nvidia.com/ai-models)

## حقائق ذات صلة

صفحة Nemotron 3 Super تذكر أن النموذج يملك 120B معاملًا إجماليًا و12B معاملًا نشطًا، ويستخدم بنية LatentMoE هجينة مع Mamba-2 وTransformer وMulti-Token Prediction. كما تذكر أن التفكير قابل للتشغيل والإيقاف عبر chat template، وأن اللغات المدعومة المعلنة هي الإنجليزية والفرنسية والألمانية والإيطالية واليابانية والإسبانية والصينية؛ العربية ليست ضمن القائمة المعلنة.

كتالوج NVIDIA الرسمي يعرض بدائل أصغر أو أسرع يمكن اختبارها لاحقًا عبر NVIDIA API، منها `nemotron-3-nano-30b-a3b` و`nemotron-3.5-lightning-30b-a3b` و`nemotron-mini-4b-instruct`، إضافة إلى نماذج عامة مثل `llama-3.1-8b-instruct` و`gpt-oss-20b`. لا يُغيّر المشروع النموذج تلقائيًا؛ يجب اختبار الجودة والعقد واللغتين قبل التبديل.

الاستنتاج العملي: لا يُتوقع أن يطابق Nemotron Super 120B زمن نموذج Flash أصغر في طلب blocking واحد، حتى مع تعطيل التفكير. التحسين الآمن داخل المشروع هو تقليل السياق في الوضع `compact`، ضبط سقف الإخراج، إبقاء `temperature=1.0` و`top_p=0.95` وفق صفحة النموذج، وقياس زمن الطلب عبر `/health` و`NVIDIA_GM_LOG_TIMING`.
