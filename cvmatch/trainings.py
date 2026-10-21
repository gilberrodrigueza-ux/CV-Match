"""Catálogo de trainings: enlaces estables del fabricante + búsquedas en Udemy y Coursera."""
from urllib.parse import quote_plus

# palabra clave (minúsculas) -> lista de (nombre, plataforma, url, gratis)
CATALOGO = {
    "azure": [
        ("Microsoft Learn — rutas de Azure", "Microsoft Learn", "https://learn.microsoft.com/en-us/training/azure/", True),
        ("AZ-305 Azure Solutions Architect Expert", "Microsoft Learn",
         "https://learn.microsoft.com/en-us/credentials/certifications/azure-solutions-architect/", True),
    ],
    "az-305": [("AZ-305 Azure Solutions Architect Expert", "Microsoft Learn",
                "https://learn.microsoft.com/en-us/credentials/certifications/azure-solutions-architect/", True)],
    "az-500": [("AZ-500 Azure Security Engineer", "Microsoft Learn",
                "https://learn.microsoft.com/en-us/credentials/certifications/azure-security-engineer/", True)],
    "az-400": [("AZ-400 DevOps Engineer Expert", "Microsoft Learn",
                "https://learn.microsoft.com/en-us/credentials/certifications/devops-engineer/", True)],
    "az-700": [("AZ-700 Azure Network Engineer", "Microsoft Learn",
                "https://learn.microsoft.com/en-us/credentials/certifications/azure-network-engineer-associate/", True)],
    "devops": [("AZ-400 DevOps Engineer Expert", "Microsoft Learn",
                "https://learn.microsoft.com/en-us/credentials/certifications/devops-engineer/", True),
               ("GitHub Skills (cursos interactivos de GitHub Actions)", "GitHub", "https://skills.github.com/", True)],
    "github": [("GitHub Skills", "GitHub", "https://skills.github.com/", True)],
    "ci/cd": [("GitHub Skills (GitHub Actions)", "GitHub", "https://skills.github.com/", True)],
    "google cloud": [
        ("Google Cloud Skills Boost", "Google Cloud", "https://www.cloudskillsboost.google/", True),
        ("Professional Cloud Architect", "Google Cloud", "https://cloud.google.com/learn/certification/cloud-architect", False),
    ],
    "gcp": [("Google Cloud Skills Boost", "Google Cloud", "https://www.cloudskillsboost.google/", True),
            ("Associate Cloud Engineer", "Google Cloud", "https://cloud.google.com/learn/certification/cloud-engineer", False)],
    "aws": [
        ("AWS Skill Builder (cientos de cursos gratis)", "AWS", "https://skillbuilder.aws/", True),
        ("AWS Solutions Architect – Associate", "AWS",
         "https://aws.amazon.com/certification/certified-solutions-architect-associate/", False),
    ],
    "terraform": [
        ("Terraform tutorials oficiales", "HashiCorp", "https://developer.hashicorp.com/terraform/tutorials", True),
        ("Terraform Associate (certificación)", "HashiCorp",
         "https://developer.hashicorp.com/certifications/infrastructure-automation", False),
    ],
    "kubernetes": [
        ("Introduction to Kubernetes (LFS158, gratis)", "Linux Foundation",
         "https://training.linuxfoundation.org/training/introduction-to-kubernetes/", True),
        ("Tutoriales oficiales de Kubernetes", "kubernetes.io", "https://kubernetes.io/docs/tutorials/", True),
        ("Certified Kubernetes Administrator (CKA)", "Linux Foundation",
         "https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/", False),
    ],
    "docker": [("Docker Get Started", "Docker", "https://docs.docker.com/get-started/", True)],
    "container": [("Docker Get Started", "Docker", "https://docs.docker.com/get-started/", True)],
    "ansible": [("Ansible Getting Started", "Red Hat / Ansible",
                 "https://docs.ansible.com/ansible/latest/getting_started/index.html", True)],
    "linux": [("Introduction to Linux (LFS101, gratis)", "Linux Foundation",
               "https://training.linuxfoundation.org/training/introduction-to-linux/", True)],
    "network": [("Cisco Networking Academy", "Cisco", "https://www.netacad.com/", True)],
    "redes": [("Cisco Networking Academy", "Cisco", "https://www.netacad.com/", True)],
    "fortinet": [("Fortinet Training Institute (NSE)", "Fortinet", "https://training.fortinet.com/", True)],
    "firewall": [("Fortinet Training Institute (NSE)", "Fortinet", "https://training.fortinet.com/", True)],
    "security": [("ISC2 Certified in Cybersecurity (CC) — training gratis", "ISC2",
                  "https://www.isc2.org/certifications/cc", True)],
    "seguridad": [("ISC2 Certified in Cybersecurity (CC) — training gratis", "ISC2",
                   "https://www.isc2.org/certifications/cc", True)],
    "oracle": [("Oracle MyLearn (OCI Foundations gratis)", "Oracle", "https://mylearn.oracle.com/", True)],
    "oci": [("Oracle MyLearn (OCI Foundations gratis)", "Oracle", "https://mylearn.oracle.com/", True)],
    "databricks": [("Databricks Academy", "Databricks", "https://www.databricks.com/learn/training/home", True)],
    "servicenow": [("ServiceNow Now Learning", "ServiceNow", "https://nowlearning.servicenow.com/", True)],
    "entra": [("SC-300 / identidad en Microsoft Learn", "Microsoft Learn",
               "https://learn.microsoft.com/en-us/training/browse/?terms=Entra%20ID", True)],
    "identity": [("Identidad en Microsoft Learn", "Microsoft Learn",
                  "https://learn.microsoft.com/en-us/training/browse/?terms=identity", True)],
    "python": [("Python for Everybody (auditable gratis)", "Coursera",
                "https://www.coursera.org/specializations/python", True)],
}


def search_links(skill):
    q = quote_plus(skill)
    return [
        (f"Buscar '{skill}' en Microsoft Learn", "Microsoft Learn",
         f"https://learn.microsoft.com/en-us/training/browse/?terms={q}", True),
        (f"Buscar '{skill}' en Google Cloud Skills Boost", "Google Cloud",
         f"https://www.cloudskillsboost.google/catalog?keywords={q}", True),
        (f"Buscar '{skill}' en Udemy", "Udemy", f"https://www.udemy.com/courses/search/?q={q}", False),
        (f"Buscar '{skill}' en Coursera", "Coursera", f"https://www.coursera.org/search?query={q}", False),
    ]


def trainings_for(skill):
    s = skill.lower()
    found, seen = [], set()
    for key, items in CATALOGO.items():
        if key in s:
            for it in items:
                if it[2] not in seen:
                    seen.add(it[2])
                    found.append(it)
    out = found[:4]
    for it in search_links(skill):
        if it[1] in ("Udemy", "Coursera") or not found:
            out.append(it)
    return [{"nombre": n, "plataforma": p, "url": u, "gratis": g} for n, p, u, g in out]
