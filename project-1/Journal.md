Date: March 11th, 2025:

Title: Cleaning and Uploading Data for SQL Analysis

For my Coursera project, I needed to demonstrate basic SQL commands—SELECT, FROM, and WHERE—using BigQuery with a public dataset. I initially chose a dataset containing San Francisco 311 requests, but I quickly ran into a problem: the most recent data only went up to August 2024, which wasn't current enough for my needs. So, I downloaded the latest dataset directly from the San Francisco 311 website, ensuring I had the most up-to-date information.

This dataset, however, came with its own set of challenges. At 3.8 GB and over 19,000 rows, it was too large to upload directly to BigQuery. After some research, I found that Google Cloud Storage (GCS) was the best workaround. But when I attempted to create a table in BigQuery, I hit another snag—column headers contained spaces, which aren't allowed.

Initially, I considered using Excel to clean up the data, but with a file this large, that wasn't feasible. Since I wasn't comfortable using Python for data cleaning just yet, I looked for another solution. I found Google Dataprep—a cloud-based tool designed for structuring and transforming raw data. Using Dataprep, I created a recipe to standardize column headers, replacing spaces with underscores. It took some trial and error, plus a few YouTube tutorials and Google searches, but I eventually figured it out.

With my cleaned dataset ready, I attempted to create the table again—only to discover another issue: incorrect timestamps. Thankfully, I now had a powerful tool in Dataprep, and after adjusting my workflow, I corrected the timestamps and finalized the dataset.

For handling missing values, I took a hybrid approach: I added "NULL" for missing cells in Dataprep, with the flexibility to convert them to "N/A" for better visualization in reporting.

After much trial and persistence, I successfully uploaded the cleaned dataset to BigQuery. I created my table, which allowed me to finally start my SQL project for my GitHub professional portfolio.

This project has been invaluable hands-on experience in data cleaning, cloud storage, and SQL, and it is an excellent example of how overcoming obstacles can turn into an opportunity to learn new tools and refine problem-solving skills.




Date: March 14th, 2025

Title: Building My GitHub Portfolio: A Journey fo Learning and Organization

New skills deserve a proper stage, and what better place than GitHub to showcase them? Since I've been diving into SQL, Google Cloud Storage (GCS), and Google Dataprep, it only made sense to add GitHub to my learning journey. But like everything else, GitHub came with its own learning curve—especially when it came to organizing my files properly.

Step 1: Setting Up My Repository
Creating a GitHub account was straightforward, but getting everything structured the way I wanted? Not so much. My first assumption was that I could simply drag and drop files, and GitHub would magically organize them for me. Turns out not entirely. I needed a structured approach to highlight different aspects of my project:
📂 Datasets – Sample data files (since my original dataset was too large).
📂 Screenshots – Visual proof of my workflow and transformations in Dataprep.
📂 Outputs – Processed files ready for BigQuery analysis.
📂 Journal – Documenting my struggles, solutions, and progress.
📂 README – A project summary for visitors.


Step 2: Creating Folders (Branches?) in GitHub
GitHub doesn't use traditional folders like a typical file system. Instead, everything revolves around branches. This was a challenge at first—I couldn't create an empty folder unless I added a file inside it. Here's the workaround I figured out:
1️⃣ Click Add File in the repository.
2️⃣ In the "Name your file…" box, type the folder name followed by a / (e.g., Datasets/).
3️⃣ GitHub won't let you commit just yet, so you need to add a placeholder file (e.g., Datasets/placeholder.txt).
4️⃣ Once the folder structure is created, I could upload actual files and delete the placeholder later.
This method worked like a charm! After some trial and error, I structured my repo exactly as I wanted it.


Step 3: Uploading Files and Handling GitHub's Size Limits
With my folders (branches?) set up, I started uploading my work. Then, another hurdle—GitHub has a file size limit of 100MB per file, meaning my original 3.8GB dataset was a no-go. To work around this, I used Google Dataprep to generate a sample dataset for people to view and analyze.
I also uploaded:
✔️ Screenshots of my workflow in Dataprep.
✔️ My cleaning recipe that transformed the dataset.
✔️ A README.md to introduce my project.


Step 4: Journaling My Progress
Now, here's something cool: GitHub allows you to create Markdown files (.md) directly in the browser! I used this to create:
📄 README.md – A structured summary of my project.
📄 Journal.md – A running log of challenges, solutions, and progress.
With this setup complete, I'm finally ready to dive into BigQuery, run some SQL queries, and start visualizing my data.


Now, I'm certain there are more efficient ways to do exactly what I just did. But when you are learning independently, with no one to ask questions to, this is the best I came up with. This project has been a fun mix of trial, error, and discovery—and it's only the beginning! 🚀
