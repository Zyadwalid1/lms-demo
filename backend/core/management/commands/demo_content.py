"""Fictional demo content for `seed_demo`. All people and companies are invented; every
email address uses example.com (reserved by RFC 2606, mail to it is never delivered).

Lecture titles starting with "Reading:" become articles; every course ends with a
knowledge-check quiz; courses with "assignment" get one.
"""

CATEGORIES = [
    ("development", "Development", "code"),
    ("business", "Business", "briefcase"),
    ("design", "Design", "palette"),
    ("it-software", "IT & Software", "server"),
    ("health-safety", "Health & Safety", "shield-check"),
    ("care-compliance", "Care & Compliance", "heart-pulse"),
]

TOPICS = ["Python", "Django", "React", "Excel", "SQL", "Project Management", "Figma", "Branding",
          "Cloud", "Security", "Git", "Fire Safety", "GDPR", "Safeguarding", "First Aid"]  # fmt: skip

INSTRUCTORS = [
    ("daniel.reeve", "Daniel Reeve", "Senior software engineer and author of 12 programming courses."),
    ("amira.haddad", "Amira Haddad", "Data analyst and certified project manager (PMP)."),
    ("leo.martins", "Leo Martins", "Product designer who has shipped apps used by millions."),
    ("priya.nair", "Priya Nair", "Cloud architect and security trainer."),
]

# quiz question: (kind, prompt, [(option, correct), ...]) ; fill_blank answers are accepted values
Q = {
    "py": [
        (
            "single_choice",
            "Which keyword defines a function in Python?",
            [("func", 0), ("def", 1), ("lambda", 0)],
        ),
        ("true_false", "Python lists are immutable.", [("True", 0), ("False", 1)]),
        ("multiple_choice", "Which are built-in Python types?", [("dict", 1), ("tuple", 1), ("array", 0)]),
        ("fill_blank", "The function that prints to the screen is ___ .", [("print", 1)]),
    ],
    "web": [
        (
            "single_choice",
            "Which HTTP method is used to create a resource?",
            [("GET", 0), ("POST", 1), ("HEAD", 0)],
        ),
        ("true_false", "A 404 status means the server crashed.", [("True", 0), ("False", 1)]),
        ("multiple_choice", "Which are valid HTTP status classes?", [("2xx", 1), ("4xx", 1), ("7xx", 0)]),
        ("short_answer", "What data format do most REST APIs return?", [("json", 1)]),
    ],
    "data": [
        (
            "single_choice",
            "Which SQL clause filters grouped rows?",
            [("WHERE", 0), ("HAVING", 1), ("ORDER BY", 0)],
        ),
        ("true_false", "A pivot table changes the source data.", [("True", 0), ("False", 1)]),
        ("multiple_choice", "Which are aggregate functions?", [("SUM", 1), ("AVG", 1), ("TRIM", 0)]),
        ("fill_blank", "To combine rows from two tables you use a ___ .", [("join", 1)]),
    ],
    "pm": [
        (
            "single_choice",
            "What does the critical path determine?",
            [("Budget", 0), ("Shortest project duration", 1), ("Team size", 0)],
        ),
        ("true_false", "Scope creep is uncontrolled growth in project scope.", [("True", 1), ("False", 0)]),
        ("multiple_choice", "Which are project constraints?", [("Time", 1), ("Cost", 1), ("Weather", 0)]),
        (
            "short_answer",
            "What do you call a document that formally starts a project?",
            [("project charter", 1), ("charter", 1)],
        ),
    ],
    "design": [
        (
            "single_choice",
            "Which principle groups related items together?",
            [("Proximity", 1), ("Contrast", 0), ("Rhythm", 0)],
        ),
        ("true_false", "Vector graphics lose quality when scaled up.", [("True", 0), ("False", 1)]),
        ("multiple_choice", "Which are colour models?", [("RGB", 1), ("CMYK", 1), ("DPI", 0)]),
        (
            "fill_blank",
            "The space between lines of text is called ___ .",
            [("leading", 1), ("line height", 1)],
        ),
    ],
    "cloud": [
        (
            "single_choice",
            "Which model gives you virtual machines to manage?",
            [("IaaS", 1), ("SaaS", 0), ("FaaS", 0)],
        ),
        (
            "true_false",
            "Multi-factor authentication reduces account takeover risk.",
            [("True", 1), ("False", 0)],
        ),
        (
            "multiple_choice",
            "Which are signs of a phishing email?",
            [("Urgent tone", 1), ("Mismatched sender", 1), ("Your own signature", 0)],
        ),
        ("short_answer", "What does the 'S' in HTTPS stand for?", [("secure", 1)]),
    ],
    "fire": [
        (
            "single_choice",
            "Which extinguisher is safe on electrical fires?",
            [("Water", 0), ("CO2", 1), ("Foam", 0)],
        ),
        ("true_false", "You should use the lift during a fire evacuation.", [("True", 0), ("False", 1)]),
        (
            "multiple_choice",
            "Which are part of the fire triangle?",
            [("Heat", 1), ("Oxygen", 1), ("Water", 0)],
        ),
        ("fill_blank", "In the UK, the emergency number is ___ .", [("999", 1), ("112", 1)]),
    ],
    "handling": [
        (
            "single_choice",
            "What should you do first before lifting?",
            [("Lift quickly", 0), ("Assess the load", 1), ("Twist your back", 0)],
        ),
        ("true_false", "Bending your knees protects your back when lifting.", [("True", 1), ("False", 0)]),
        (
            "multiple_choice",
            "TILE stands for Task, Individual, Load and ...",
            [("Environment", 1), ("Equipment", 0), ("Effort", 0)],
        ),
        (
            "short_answer",
            "Which part of your body takes most strain when lifting badly?",
            [("back", 1), ("lower back", 1)],
        ),
    ],
    "gdpr": [
        (
            "single_choice",
            "How long do you have to report a notifiable breach to the ICO?",
            [("72 hours", 1), ("7 days", 0), ("30 days", 0)],
        ),
        ("true_false", "A name and email address are personal data.", [("True", 1), ("False", 0)]),
        (
            "multiple_choice",
            "Which are lawful bases for processing?",
            [("Consent", 1), ("Contract", 1), ("Curiosity", 0)],
        ),
        (
            "short_answer",
            "What does SAR stand for? (subject access ...)",
            [("request", 1), ("subject access request", 1)],
        ),
    ],
    "care": [
        (
            "single_choice",
            "What is the most effective way to prevent infection spread?",
            [("Hand hygiene", 1), ("Air freshener", 0), ("Open windows", 0)],
        ),
        (
            "true_false",
            "You must report safeguarding concerns even if you are unsure.",
            [("True", 1), ("False", 0)],
        ),
        (
            "multiple_choice",
            "Which are types of abuse?",
            [("Financial", 1), ("Neglect", 1), ("Punctuality", 0)],
        ),
        (
            "fill_blank",
            "Concerns are reported to the designated safeguarding ___ .",
            [("lead", 1), ("officer", 1)],
        ),
    ],
}

ASSIGN = (
    "<p>Apply what you learned to a real example from your own work or life.</p>"
    "<ul><li>Describe the situation in 150-300 words</li><li>Explain the steps you took</li>"
    "<li>Attach a screenshot or document if useful</li></ul>"
)


def course(slug, title, subtitle, category, level, tier, quiz, sections, owner=None, topics=(), cpd=None,
           free=False, assignment=False):  # fmt: skip
    return {"slug": slug, "title": title, "subtitle": subtitle, "category": category, "level": level, "tier": tier,
            "quiz": quiz, "sections": sections, "owner": owner, "topics": list(topics), "cpd": cpd, "free": free,
            "assignment": assignment}  # fmt: skip


MARKETPLACE = [
    course(
        "python-for-absolute-beginners",
        "Python for Absolute Beginners",
        "Write your first real programs in a weekend",
        "development",
        "beginner",
        5,
        "py",
        [
            (
                "Getting started",
                ["Welcome and course overview", "Installing Python", "Reading: How to use this course"],
            ),
            ("Core building blocks", ["Variables and types", "Lists and dictionaries", "Loops", "Functions"]),
            (
                "Your first project",
                ["Planning a to-do app", "Building it step by step", "Reading: Where to go next"],
            ),
        ],
        owner="daniel.reeve",
        topics=["Python"],
        assignment=True,
    ),
    course(
        "rest-apis-with-django",
        "Build REST APIs with Django",
        "Design, secure and ship production APIs",
        "development",
        "intermediate",
        8,
        "web",
        [
            (
                "API foundations",
                ["How HTTP really works", "Designing resources", "Reading: Status codes cheat sheet"],
            ),
            (
                "Building the API",
                ["Models and migrations", "Endpoints and validation", "Authentication", "Pagination"],
            ),
            ("Going to production", ["Testing your API", "Performance and caching", "Deploying"]),
        ],
        owner="daniel.reeve",
        topics=["Django", "Python"],
        assignment=True,
    ),
    course(
        "react-fundamentals",
        "React Fundamentals",
        "Components, state and hooks from zero",
        "development",
        "beginner",
        7,
        "web",
        [
            ("Thinking in components", ["Why React", "Your first component", "Props"]),
            ("State and effects", ["useState", "useEffect", "Reading: Rules of hooks"]),
            ("A small app", ["Fetching data", "Forms", "Putting it together"]),
        ],
        owner="daniel.reeve",
        topics=["React"],
    ),
    course(
        "git-and-github-basics",
        "Git & GitHub Basics",
        "Version control without the fear",
        "development",
        "beginner",
        None,
        "web",
        [
            (
                "Git essentials",
                ["What version control solves", "Commits and branches", "Reading: Everyday commands"],
            ),
        ],
        owner="daniel.reeve",
        topics=["Git"],
        free=True,
    ),
    course(
        "excel-for-data-analysis",
        "Excel for Data Analysis",
        "Formulas, pivots and dashboards that answer questions",
        "business",
        "beginner",
        4,
        "data",
        [
            ("Excel foundations", ["Tidy data", "Essential formulas", "Reading: Keyboard shortcuts"]),
            ("Analysis", ["Pivot tables", "Lookups", "Charts that persuade"]),
        ],
        owner="amira.haddad",
        topics=["Excel"],
        assignment=True,
    ),
    course(
        "sql-for-analysts",
        "SQL for Analysts",
        "Query any database with confidence",
        "business",
        "intermediate",
        5,
        "data",
        [
            ("Querying", ["SELECT and WHERE", "Sorting and limiting", "Aggregates and GROUP BY"]),
            ("Combining data", ["Joins explained", "Subqueries", "Reading: Window functions primer"]),
        ],
        owner="amira.haddad",
        topics=["SQL"],
    ),
    course(
        "project-management-essentials",
        "Project Management Essentials",
        "Plan, run and deliver projects on time",
        "business",
        "all",
        6,
        "pm",
        [
            ("Starting right", ["What a project is", "The project charter", "Stakeholders"]),
            (
                "Planning and delivery",
                [
                    "Scope and WBS",
                    "Scheduling and the critical path",
                    "Managing risk",
                    "Reading: Templates pack",
                ],
            ),
        ],
        owner="amira.haddad",
        topics=["Project Management"],
        assignment=True,
    ),
    course(
        "ui-design-in-figma",
        "UI Design in Figma",
        "From wireframe to polished interface",
        "design",
        "beginner",
        6,
        "design",
        [
            ("Design basics", ["Layout and grids", "Typography", "Colour"]),
            ("Working in Figma", ["Frames and auto layout", "Components and variants", "Prototyping"]),
        ],
        owner="leo.martins",
        topics=["Figma"],
        assignment=True,
    ),
    course(
        "brand-identity-design",
        "Brand Identity Design",
        "Create a memorable visual identity",
        "design",
        "intermediate",
        5,
        "design",
        [
            ("Strategy", ["What a brand is", "Research and positioning"]),
            (
                "Visual identity",
                ["Logo design process", "Colour and type systems", "Reading: Brand guidelines template"],
            ),
        ],
        owner="leo.martins",
        topics=["Branding"],
    ),
    course(
        "cloud-computing-fundamentals",
        "Cloud Computing Fundamentals",
        "Understand the cloud and its building blocks",
        "it-software",
        "beginner",
        7,
        "cloud",
        [
            ("Concepts", ["What the cloud is", "IaaS, PaaS and SaaS", "Reading: Shared responsibility"]),
            ("Core services", ["Compute", "Storage", "Networking", "Cost control"]),
        ],
        owner="priya.nair",
        topics=["Cloud"],
    ),
    course(
        "cybersecurity-essentials",
        "Cybersecurity Essentials",
        "Protect yourself and your organisation",
        "it-software",
        "beginner",
        4,
        "cloud",
        [
            ("Threats", ["Phishing", "Passwords and MFA", "Malware"]),
            ("Staying safe", ["Safe browsing", "Reporting incidents", "Reading: Security checklist"]),
        ],
        owner="priya.nair",
        topics=["Security"],
    ),
]

LIBRARY = [  # platform-owned compliance library (sold to companies; individuals can buy too)
    course(
        "fire-safety-awareness",
        "Fire Safety Awareness",
        "Prevent fires and know what to do if one starts",
        "health-safety",
        "all",
        3,
        "fire",
        [
            ("Understanding fire", ["The fire triangle", "Common causes at work"]),
            (
                "Taking action",
                ["Raising the alarm", "Using extinguishers", "Evacuation", "Reading: Fire safety log"],
            ),
        ],
        topics=["Fire Safety"],
        cpd=1.0,
    ),
    course(
        "manual-handling",
        "Manual Handling",
        "Lift, carry and move safely",
        "health-safety",
        "all",
        3,
        "handling",
        [
            ("Risks", ["Why injuries happen", "The TILE assessment"]),
            ("Safe technique", ["Good lifting technique", "Team lifts", "Using equipment"]),
        ],
        topics=["First Aid"],
        cpd=1.0,
    ),
    course(
        "gdpr-essentials",
        "GDPR Essentials",
        "Handle personal data lawfully",
        "care-compliance",
        "all",
        3,
        "gdpr",
        [
            ("The basics", ["What personal data is", "The seven principles", "Lawful bases"]),
            ("In practice", ["Subject access requests", "Data breaches", "Reading: Do and don't list"]),
        ],
        topics=["GDPR"],
        cpd=1.5,
    ),
    course(
        "safeguarding-adults",
        "Safeguarding Adults",
        "Recognise, respond to and report abuse",
        "care-compliance",
        "all",
        3,
        "care",
        [
            ("Recognising abuse", ["Types of abuse", "Signs and indicators"]),
            ("Responding", ["What to do and say", "Reporting and recording", "Reading: Local contacts"]),
        ],
        topics=["Safeguarding"],
        cpd=2.0,
    ),
    course(
        "infection-prevention-and-control",
        "Infection Prevention and Control",
        "Stop the spread of infection",
        "care-compliance",
        "all",
        3,
        "care",
        [
            ("Principles", ["How infections spread", "Hand hygiene"]),
            ("Practice", ["PPE", "Cleaning and waste", "Reading: Outbreak checklist"]),
        ],
        topics=["First Aid"],
        cpd=1.0,
    ),
    course(
        "health-and-safety-at-work",
        "Health and Safety at Work",
        "Your rights and responsibilities",
        "health-safety",
        "all",
        3,
        "fire",
        [
            ("The law", ["Employer and employee duties", "Risk assessment"]),
            (
                "Everyday safety",
                ["Slips, trips and falls", "Display screen equipment", "Reporting accidents"],
            ),
        ],
        topics=["Fire Safety"],
        cpd=1.0,
    ),
]

COMPANIES = [
    {
        "name": "Brightwater Care Group",
        "slug": "brightwater-care",
        "domain": "brightwater.example.com",
        "hr": ("hana.cole", "Hana Cole"),
        # (region, [sites]) ; each site gets a Care team and a Nursing team
        "tree": [("North", ["Leeds", "York"]), ("South", ["Brighton", "Bristol"])],
        "teams": ["Care team", "Nursing team"],
        "roles": ["Care Assistant", "Senior Carer", "Nurse", "Cook", "Manager"],
        "people": 42,
        "induction": course(
            "brightwater-induction",
            "Brightwater Induction",
            "Welcome to Brightwater Care Group",
            "care-compliance",
            "all",
            None,
            "care",
            [
                ("Welcome", ["Our values", "Your first week", "Reading: Staff handbook"]),
            ],
        ),  # fmt: skip
        "requirements": [  # (course slug, name, renewal months, target: "all" | ("role", name) | ("unit", name))
            ("fire-safety-awareness", "Fire Safety", 12, "all"),
            ("safeguarding-adults", "Safeguarding Adults", 24, "all"),
            ("infection-prevention-and-control", "Infection Control", 12, ("unit", "Care team")),
            ("manual-handling", "Manual Handling", 12, ("role", "Care Assistant")),
            ("gdpr-essentials", "GDPR", 24, ("role", "Manager")),
            ("brightwater-induction", "Induction", None, "all"),
        ],
    },
    {
        "name": "Northwind Logistics",
        "slug": "northwind-logistics",
        "domain": "northwind.example.com",
        "hr": ("omar.price", "Omar Price"),
        "tree": [("Operations", ["Manchester Hub", "Birmingham Hub"]), ("Head Office", [])],
        "teams": ["Warehouse", "Drivers"],
        "roles": ["Warehouse Operative", "Driver", "Team Leader", "Office Staff"],
        "people": 26,
        "induction": None,
        "requirements": [
            ("health-and-safety-at-work", "Health & Safety", 12, "all"),
            ("manual-handling", "Manual Handling", 12, ("unit", "Warehouse")),
            ("fire-safety-awareness", "Fire Safety", 12, "all"),
            ("cybersecurity-essentials", "Cyber Security", 12, ("role", "Office Staff")),
        ],
    },
]

FIRST = ["Sara", "James", "Aisha", "Tom", "Mei", "Lucas", "Fatima", "Noah", "Chloe", "Ethan", "Zara", "Oliver",
         "Amelia", "Yusuf", "Grace", "Leo", "Isla", "Arjun", "Ruby", "Kai", "Hannah", "Omar", "Sofia", "Jack",
         "Layla", "Ben", "Maya", "Sam", "Nadia", "Ryan"]  # fmt: skip
LAST = ["Ahmed", "Smith", "Khan", "Jones", "Chen", "Silva", "Ali", "Brown", "Taylor", "Wilson", "Patel", "Evans",
        "Hughes", "Malik", "Walker", "Wright", "Hall", "Shah", "Green", "Wood", "Clarke", "Lewis", "Young", "King"]  # fmt: skip

REVIEWS = [
    (5, "Clear, practical and well paced. Exactly what I needed."),
    (5, "The best course I have taken on this topic."),
    (4, "Great content, a few lectures could be shorter."),
    (4, "Very useful examples. Would recommend."),
    (5, "The instructor explains things simply. Loved the quizzes."),
    (3, "Good overview but I wanted more advanced material."),
    (4, "Solid course, the project at the end tied it all together."),
    (5, "Finally understand this. Thank you!"),
]
QUESTIONS = [
    ("Is there a downloadable version of the slides?", "Yes, they are in the resources tab of each lecture."),
    (
        "I get an error at step 3, any idea why?",
        "Check the version you installed; the course uses the latest one.",
    ),
    ("How long should the final project take?", "Most learners finish it in two to three hours."),
]
