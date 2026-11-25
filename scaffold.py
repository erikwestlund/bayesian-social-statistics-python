"""Project setup, run by framework.scaffold() after the settings are loaded.

Put code here that every notebook and script needs, such as plotting styles.
Random seeds are set from settings/scaffold.yml (seed_on_scaffold and seed).
"""

import seaborn as sns

# Colorblind-safe palette and a light grid for every figure
sns.set_theme(style="whitegrid", palette="colorblind")
