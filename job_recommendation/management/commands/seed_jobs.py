from django.core.management.base import BaseCommand

from job_recommendation.models import Job


SAMPLE_JOBS = [
    {
        "title": "Python Backend Developer",
        "description": "Build and maintain backend services with Python and Django.",
        "skills_required": ["Python", "Django", "REST API", "SQL"],
    },
    {
        "title": "Django Full Stack Developer",
        "description": "Work across frontend and backend layers for web applications.",
        "skills_required": ["Python", "Django", "HTML", "CSS", "JavaScript"],
    },
    {
        "title": "Data Analyst",
        "description": "Analyze business data and create insights dashboards.",
        "skills_required": ["SQL", "Python", "Pandas", "Tableau"],
    },
    {
        "title": "Machine Learning Engineer",
        "description": "Develop ML pipelines and deploy predictive models.",
        "skills_required": ["Python", "Pandas", "NumPy", "Scikit-learn", "Docker"],
    },
    {
        "title": "DevOps Engineer",
        "description": "Support CI/CD pipelines and cloud deployment workflows.",
        "skills_required": ["Docker", "Kubernetes", "AWS", "Jenkins", "Git"],
    },
    {
        "title": "Cloud Engineer",
        "description": "Design and support cloud-native infrastructure solutions.",
        "skills_required": ["AWS", "Azure", "GCP", "Docker", "Kubernetes"],
    },
    {
        "title": "Backend Engineer",
        "description": "Implement scalable APIs and database-driven features.",
        "skills_required": ["Python", "SQL", "REST API", "PostgreSQL"],
    },
    {
        "title": "AI Engineer",
        "description": "Integrate AI services and productionize assistant workflows.",
        "skills_required": ["Python", "TensorFlow", "PyTorch", "Docker"],
    },
]


class Command(BaseCommand):
    help = "Seed the job table with sample roles for resume matching demos."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for job_data in SAMPLE_JOBS:
            job, created = Job.objects.update_or_create(
                title=job_data["title"],
                defaults={
                    "description": job_data["description"],
                    "skills_required": job_data["skills_required"],
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(SAMPLE_JOBS)} jobs ({created_count} created, {updated_count} updated)."
            )
        )