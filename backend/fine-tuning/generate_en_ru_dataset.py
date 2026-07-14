import json
import random

ACADEMIC_PAIRS = [
    ("Explain the impact of quantum entanglement on information theory.", "Объясните влияние квантовой запутанности на теорию информации."),
    ("The study reveals a statistically significant correlation between variables.", "Исследование выявляет статистически значимую корреляцию между переменными."),
    ("This hypothesis assumes a uniform distribution of the underlying data.", "Данная гипотеза предполагает равномерное распределение исходных данных."),
    ("We must critically evaluate the epistemological foundations of this paradigm.", "Мы должны критически оценить эпистемологические основы этой парадигмы."),
    ("A longitudinal approach was adopted to observe the phenomena over a decade.", "Для наблюдения за явлениями в течение десятилетия был применен лонгитюдный подход.")
]

PROFESSIONAL_PAIRS = [
    ("Please deploy the Kubernetes cluster to the staging environment.", "Пожалуйста, разверните кластер Kubernetes в промежуточной среде."),
    ("The quarterly financial audit indicates a positive cash flow.", "Ежеквартальный финансовый аудит указывает на положительный денежный поток."),
    ("Ensure the SLA requirements are met for the API gateway.", "Убедитесь, что требования SLA для API-шлюза соблюдены."),
    ("We need to synergize our cross-functional teams to meet the Q3 OKRs.", "Нам необходимо объединить усилия наших кросс-функциональных команд для выполнения OKR третьего квартала."),
    ("The pull request has been approved and merged into the main branch.", "Pull request был одобрен и объединен с основной веткой.")
]

COLLOQUIAL_PAIRS = [
    ("Hey, what's up? Long time no see!", "Привет, как дела? Давно не виделись!"),
    ("I'm totally exhausted, going to hit the sack.", "Я совершенно вымотан, пойду на боковую."),
    ("That movie was mind-blowing, seriously.", "Этот фильм был просто отвал башки, серьезно."),
    ("Let's grab a bite to eat after work.", "Давай перекусим после работы."),
    ("No worries, it's a piece of cake.", "Не парься, это проще простого.")
]

def generate_dataset_for_style(output_path: str, pairs, style: str, count: int = 5500):
    with open(output_path, 'w', encoding='utf-8') as f:
        for _ in range(count):
            en, ru = random.choice(pairs)
            
            instructions = [
                "Translate to Russian:",
                "Provide the Russian translation for:",
                "How do you say this in Russian in a {} style:".format(style),
                f"[{style.upper()}] Translate to RU:"
            ]
            
            record = {
                "instruction": random.choice(instructions),
                "input": en,
                "output": ru,
                "metadata": {"style": style}
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Generated {count} records in {output_path}")

if __name__ == "__main__":
    generate_dataset_for_style("academic.jsonl", ACADEMIC_PAIRS, "academic")
    generate_dataset_for_style("professional.jsonl", PROFESSIONAL_PAIRS, "professional")
    generate_dataset_for_style("colloquial.jsonl", COLLOQUIAL_PAIRS, "colloquial")
