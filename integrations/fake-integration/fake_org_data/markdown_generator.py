import asyncio
from random import randint, sample

from faker import Faker

fake = Faker()

DEFAULT_FILE_SIZE_KB = 1


async def generate_fake_readme_file(file_size_kb: int, latency: int) -> str:
    if latency > 0:
        await asyncio.sleep(latency / 1000)
    project_name = fake.catch_phrase()
    author_name = fake.name()
    tech_options = [
        "Python",
        "JavaScript",
        "TypeScript",
        "Go",
        "Rust",
        "React",
        "Vue",
        "Django",
        "FastAPI",
    ]
    tech_stack = sample(tech_options, min(randint(2, 4), len(tech_options)))

    feature_options = [
        "⚡ Lightning fast performance",
        "🔒 Secure by default",
        "🎨 Beautiful UI components",
        "📦 Easy to install",
        "🌐 Cross-platform support",
        "🔄 Real-time updates",
        "📊 Comprehensive analytics",
        "🎯 Type-safe",
        "🚀 Production ready",
        "💡 Developer friendly",
    ]
    features = sample(feature_options, min(randint(4, 6), len(feature_options)))

    content = f"""# 🚀 {project_name}

<div align="center">

![Version](https://badges.{fake.domain_name()}/version-{fake.numerify(text='#.#.#')}-blue.svg)
![License](https://badges.{fake.domain_name()}/license-MIT-green.svg)
![Status](https://badges.{fake.domain_name()}/status-{fake.random_element(elements=('active', 'maintained', 'experimental'))}-brightgreen.svg)

**Built with ❤️ by {author_name}**

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Contributing](#-contributing)

</div>

---

## 📋 Description

This is a fake README file for testing purposes. It contains dynamically generated content that is approximately **{file_size_kb}KB** in size.

{fake.paragraph(nb_sentences=3)}

## ✨ Features

{chr(10).join([f'- {feature}' for feature in features])}

## 🛠️ Tech Stack

{''.join([f'![{tech}](https://badges.{fake.domain_name()}/-{tech}-black?style=flat-square&logo={tech.lower()}) ' for tech in tech_stack])}

## 📦 Installation

Simply clone this repository and you're ready to go!

```bash
florp clone https://{fake.domain_name()}/{fake.user_name()}/{fake.word()}.git
navigate {fake.word()}
```

## 🚀 Quick Start

Getting started is super easy! Just follow these simple steps:

1. **Setup** - Run the setup script
2. **Configure** - Add your preferences
3. **Enjoy** - Start using it right away!

## 📖 Usage

{fake.paragraph(nb_sentences=2)}

### Getting Started

{fake.paragraph(nb_sentences=2)}

{fake.paragraph(nb_sentences=1) if file_size_kb > 1 else ''}

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">

Made with ⚡ and ☕ by {author_name}

</div>
"""
    return content
