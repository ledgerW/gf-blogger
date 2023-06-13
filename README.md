# Getting Started  

## Install  
  
### Pull Repo  
`git clone https://github.com/ledgerW/gf-blogger.git`

### Python  
1. Install Anaconda  

2. Create a virtual conda environment for this project:  
From project root: `conda env create -f environment.yml`  
Activate env: `activate gf-blogger`  


### .env  
Get API keys for the below services and put them in the `.env` (below)  
[OpenAI](https://openai.com/)  
[Serper](https://serper.dev/)  

Populate `goldfinch_blogger/.env.template` and rename to `.env` (keep in `goldfinch_blogger/`)  


### Input  
There are two examples:  
- `goldfinch_blogger/outline.txt`  
- `goldfinch_blogger/section.txt`  

The `SECTION:` string is used for parsing sections, so it must be used. Just keep the format in the 
examples, but otherwise anything can go in the section description.  

These are the input for the "blog writer". The file can be called anything. A relative path to it will
be passed to the "blog writer" CLI from the terminal  

### Output  
Output will be found in `goldfinch_blogger/new_post/` (it will be created). 
It will produce the final blog post, which will be called `blog.txt`, as well as files containing
individual sections and the final prompts containing all the stuffed context for each section, which
will located in `goldfinch_blogger/new_post/sections/`.  

### Example Usage  
from `./goldfinch_blogger`: `python GoldfinchBlogger.py --outline_path outline.txt`  


***  
**Notes**  
- Here's an example of how all this can be deployed fully serverless with backend and frontend CI/CD using Seed and Vercel...  
[Oxpecker](https://github.com/ledgerW/oxpecker)  
(This is a private repo - I'll send you an invite)