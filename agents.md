# Research Agents

## Agent: ivy_2028
- Schedule: Monday 6:03 AM (Hermes cron: ivy-2028-weekly-pipeline)
- URL verification: Keenable (tier-1, agentic fetch busts bot walls) → Firecrawl (tier-2) → HTTP (tier-3), integrated in coordinator.py; dead links eliminated from digest
- Post-step: none (verification is inside coordinator now)
- Profile: Indian origin, parents immigrated to US, US citizen, CT-based, 10th grade (rising 11th, Class of 2028), high income family, 4.0+ GPA, interests: biology, law, fencing, willing to travel/overnight
- Exclusions: low-income-only, need-based, Pell Grant, college-only, senior-only
- Ethnic tagging: yes (indian_american, asian_american, south_asian, kids_of_immigrants, minority, heritage)
- Coordinator: `cd ~/projects/ivy-2028-v2 && python3.13 coordinator.py --agent ivy_2028 --date $(date +%Y-%m-%d)`

### Categories

**1. science_math**
Search terms: biology olympiad, USABO, AMC, Science Olympiad, ISEF, science fair, research competitions, STEM contests, CT Science Fair

**2. scholarships**
Search terms: national merit, merit scholarship, Indian American scholarship, CT scholarship, Asian/South Asian heritage scholarships, scholarships for children of immigrants
Notes: Filter out low-income-only, need-based, Pell Grant. Keep merit, academic, leadership, Indian American heritage, Asian heritage.

**3. law_civics**
Search terms: mock trial, debate, constitutional law, model congress, moot court, civics bee, supreme court, CT mock trial, Yale law programs

**4. exams**
Search terms: PSAT, SAT, ACT, AP, CLT, PSAT/NMSQT dates and registration

**5. writing_humanities**
Search terms: writing competitions, essay contests, Scholastic Art Writing, National History Day, journalism, poetry

**6. summer_programs**
Search terms: biology summer programs 2027, research internships, pre-college, RSI, SSP, Yale summer, NIH, law summer programs

**7. general_competitions**
Search terms: Regeneron STS, National Merit, Coca Cola, Davidson Fellows, presidential scholars
Notes: Filter out low-income-only.

**8. ct_local**
Search terms: CT scholarships, Yale CT programs, UConn research, New England competitions, CT science fair

**9. fencing**
Search terms: USA Fencing tournaments, CT fencing competitions, New England circuit, Junior Olympics, NAC series, fencing camps, CT high school fencing

### Extraction Schema
Each subagent must extract these fields per opportunity:
- name, category, url, snippet, deadline, cost, aid, eligibility, eligibility_note, notes, source
- ethnic_tags: comma-separated — set if the program targets specific ethnic/cultural groups. Values: indian_american, asian_american, south_asian, kids_of_immigrants, minority, heritage

Write JSON array to `/tmp/ivy-2028/<agent>/<date>/<category>.json`.

### Execution Flow

1. **Create artifacts directory**: `mkdir -p /tmp/ivy-2028/ivy_2028/$(date +%Y-%m-%d)`
2. **Spawn 9 subagents in parallel** — one per category above. Each agent:
   - Uses WebSearch + WebFetch to find real opportunities (reads actual page content)
   - Filters out low-income-only / need-based programs per category notes
   - Extracts all fields from the schema above
   - Writes JSON array to the artifact path for its category
3. **Run coordinator**: execute the Coordinator command from the agent header
4. **Report summary**: total opportunities, urgent items, standout finds for biology/law/fencing, notable changes vs last week
