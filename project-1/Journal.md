Date: March 14th, 2025:

Title: Cleaning and Uploading Data for SQL Analysis

For my Coursera project, I needed to demonstrate basic SQL commands—SELECT, FROM, and WHERE—using BigQuery with a public dataset. I initially chose a dataset containing San Francisco 311 requests, but I quickly ran into a problem: the most recent data only went up to August 2024, which wasn't current enough for my needs. So, I downloaded the latest dataset directly from the San Francisco 311 website, ensuring I had the most up-to-date information.

This dataset, however, came with its own set of challenges. At 3.8 GB and over 19,000 rows, it was too large to upload directly to BigQuery. After some research, I found that Google Cloud Storage (GCS) was the best workaround. But when I attempted to create a table in BigQuery, I hit another snag—column headers contained spaces, which aren't allowed.

Initially, I considered using Excel to clean up the data, but with a file this large, that wasn't feasible. Since I wasn't comfortable using Python for data cleaning just yet, I looked for another solution. I found Google Dataprep—a cloud-based tool designed for structuring and transforming raw data. Using Dataprep, I created a recipe to standardize column headers, replacing spaces with underscores. It took some trial and error, plus a few YouTube tutorials and Google searches, but I eventually figured it out.

With my cleaned dataset ready, I attempted to create the table again—only to discover another issue: incorrect timestamps. Thankfully, I now had a powerful tool in Dataprep, and after adjusting my workflow, I corrected the timestamps and finalized the dataset.

For handling missing values, I took a hybrid approach: I added "NULL" for missing cells in Dataprep, with the flexibility to convert them to "N/A" for better visualization in reporting.

After much trial and persistence, I successfully uploaded the cleaned dataset to BigQuery. I created my table, which allowed me to finally start my SQL project for my GitHub professional portfolio.

This project has been invaluable hands-on experience in data cleaning, cloud storage, and SQL, and it is an excellent example of how overcoming obstacles can turn into an opportunity to learn new tools and refine problem-solving skills.
