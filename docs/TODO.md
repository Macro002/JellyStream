# SerienStream Project - Roadmap & TODO

## Current Status

### Completed Features ✅

#### Core Infrastructure
- [x] Series catalog scraper (10,267 series)
- [x] Season/episode structure scraper
- [x] Stream URL scraper (multiple languages & providers)
- [x] JSON database structurer (162MB database)
- [x] Database updater (incremental updates)
- [x] Jellyfin folder structure generator
- [x] Streaming API with Flask
- [x] VOE provider integration
- [x] HLS stream caching (1 hour TTL)
- [x] Systemd service for API
- [x] Jellyfin stack overflow fix (8MB thread stack)

#### Data Collection
- [x] **10,267 series** indexed
- [x] **253,880 episodes** scraped
- [x] **1,603 movies** scraped
- [x] **358,098 stream redirects** cataloged
- [x] Multi-language support (German, English, German subs)
- [x] Multiple hosting providers per episode

#### Jellyfin Integration
- [x] .strm file generation
- [x] Language prioritization (German → English → German subs)
- [x] Large library support (10,000+ series without crash)
- [x] Automated folder structure

---

#### Multi-Site Platform (November 2024)
- [x] **Project restructure** - Site-specific directories
- [x] **Multi-site API** - Auto-loads all site databases
- [x] **Aniworld structure** - Ready for anime scraping
- [x] **Documentation update** - Multi-site architecture guide

---

## In Progress 🚧

### Aniworld Integration (Anime)
**Status:** Structure ready, needs HTML selector adaptation

**Completed:**
- [x] Site structure cloned from serienstream
- [x] Config updated with anime-specific settings
- [x] Languages: Deutsch, German Sub, English Sub
- [x] Providers: VOE, Filemoon, Vidmoly

**Remaining:**
- [ ] Adapt HTML selectors in scrapers 1-3 for aniworld.to
- [ ] Test scraping with small sample (--limit 5)
- [ ] Create Filemoon provider (api/providers/filemoon.py)
- [ ] Create Vidmoly provider (api/providers/vidmoly.py)
- [ ] Full scrape and database generation
- [ ] Generate Jellyfin structure

**Priority:** High

---

## Planned Features 📋

### High Priority

#### FlareSolverr Integration (Future/If Needed)
**Status:** Removed for now - not needed as direct requests work

**If Cloudflare blocking occurs in future:**
- [ ] Re-implement FlareSolverr client library
- [ ] Add smart request handler with automatic fallback
- [ ] Integrate into scrapers 1-3
- [ ] Add fallback to api/redirector.py

**Priority:** Low (only if sites start blocking)

#### 1. Complete Aniworld Integration
**Goal:** Add anime streaming support from Aniworld (aniworld.to)

**Tasks:**
- [x] Clone serienstream structure to sites/aniworld
- [x] Update config for anime-specific settings
- [ ] Adapt HTML selectors for aniworld.to
  - Update `1_catalog_scraper.py`
  - Update `2_url_season_episode_num.py`
  - Update `3_language_streamurl.py`
- [ ] Create provider modules
  - `api/providers/filemoon.py`
  - `api/providers/vidmoly.py`
- [ ] Test scraping with small sample
- [ ] Full database scrape
- [ ] Generate Jellyfin library structure

**Benefits:**
- Unified platform for series + anime
- Leverage existing infrastructure
- API already supports multi-site

**Estimated Effort:** 1-2 weeks (structure done, just need scraping)

---

#### 2. Multi-Provider Support
**Goal:** Support additional hosting providers beyond VOE

**Providers to Add:**
- [ ] Streamtape
- [ ] Vidoza
- [ ] Doodstream
- [ ] Upstream

**Tasks:**
- [ ] Create provider modules for each
- [ ] Add provider fallback logic (try VOE → Streamtape → Vidoza)
- [ ] Test stream quality and reliability
- [ ] Add provider preference to config

**Benefits:**
- Better reliability (fallback if one provider is down)
- Faster streams (can choose fastest provider)
- Less dependence on single provider

**Estimated Effort:** 1-2 weeks

---

#### 3. Automatic Database Updates
**Goal:** Keep database fresh with daily/weekly updates

**Tasks:**
- [ ] Create cron job for `5_updater.py`
- [ ] Add change detection (new episodes, new series)
- [ ] Implement incremental Jellyfin updates
  - Only regenerate changed series
  - Trigger partial library scan
- [ ] Add update notifications
  - Log new content
  - Send webhook/email on updates

**Schedule:**
- Daily: Check for new episodes
- Weekly: Full database refresh
- Monthly: Cleanup dead links

**Estimated Effort:** 1 week

---

### Medium Priority

#### 4. Enhanced API Features

**Tasks:**
- [ ] Add search endpoint (`/search?q=series+name`)
- [ ] Add random episode endpoint (`/random`)
- [ ] Add recently added endpoint (`/recent`)
- [ ] Add provider status endpoint (`/providers/status`)
- [ ] Add stream quality selection
- [ ] Add subtitle support

**Estimated Effort:** 1 week

---

#### 5. Web Dashboard
**Goal:** Monitor and manage the system via web UI

**Features:**
- [ ] API statistics dashboard
- [ ] Database status (series count, last update)
- [ ] Provider health monitoring
- [ ] Manual update triggers
- [ ] Search interface
- [ ] Stream testing tool

**Tech Stack:** React or vanilla JS + Flask backend

**Estimated Effort:** 2-3 weeks

---

#### 6. Performance Optimizations

**Tasks:**
- [ ] Database indexing for faster lookups
- [ ] Redis caching layer
  - Cache redirect resolutions
  - Cache provider responses
- [ ] Parallel scraping (multiprocessing)
- [ ] Optimize Jellyfin structure generation
  - Incremental updates only
  - Skip unchanged series

**Estimated Effort:** 1-2 weeks

---

### Low Priority

#### 7. Subtitles Integration
**Goal:** Download and serve subtitles for episodes

**Tasks:**
- [ ] Scrape subtitle URLs from SerienStream
- [ ] Download and store .srt files
- [ ] Serve subtitles via API
- [ ] Add subtitle paths to .strm metadata

**Estimated Effort:** 2 weeks

---

#### 8. Quality Metrics
**Goal:** Track stream quality and reliability

**Tasks:**
- [ ] Log stream success/failure rates
- [ ] Track buffering/loading times
- [ ] Provider uptime monitoring
- [ ] Quality reports (weekly/monthly)

**Estimated Effort:** 1 week

---

#### 9. Mobile App (Future)
**Goal:** Native mobile app for browsing/streaming

**Features:**
- Browse series catalog
- Search functionality
- Direct streaming (bypass Jellyfin)
- Download for offline viewing

**Tech Stack:** React Native or Flutter

**Estimated Effort:** 6-8 weeks

---

## Technical Debt 🔧

### Code Quality
- [ ] Add comprehensive logging
- [ ] Add error handling and retries
- [ ] Write unit tests for scrapers
- [ ] Write integration tests for API
- [ ] Add type hints (Python 3.10+)
- [ ] Code documentation (docstrings)

### Infrastructure
- [ ] Set up proper backup system
  - Backup database daily
  - Backup configuration
- [ ] Add monitoring (Prometheus/Grafana)
- [ ] Set up alerting (failed scrapes, API errors)
- [ ] Docker/Docker Compose support
- [ ] CI/CD pipeline

### Security
- [ ] Add API authentication (API keys)
- [ ] Rate limiting on API endpoints
- [ ] Input validation and sanitization
- [ ] HTTPS support
- [ ] Secrets management (env vars)

---

## Feature Requests 💡

Have a feature idea? Add it here!

### Community Requests
- [ ] Support for other streaming sites (suggestions welcome)
- [ ] Bulk download support
- [ ] Watchlist/favorites system
- [ ] Episode progress tracking
- [ ] Multi-user support

---

## Completed Milestones 🎉

### v1.0 - Initial Release (June 2024)
- ✅ Full scraping pipeline
- ✅ JSON database
- ✅ VOE provider support

### v1.1 - Jellyfin Integration (November 2024)
- ✅ Jellyfin structure generator
- ✅ Streaming API
- ✅ 10,267 series support
- ✅ Stack overflow fix for large libraries

### v1.2 - FlareSolverr (Current)
- ✅ FlareSolverr infrastructure
- 🚧 Full scraper integration (in progress)

---

## Next Release: v1.3 - Aniworld Integration (Q1 2025)

**Target Date:** January 2025

**Goals:**
- [ ] Aniworld scraper complete
- [ ] Anime Jellyfin library
- [ ] Combined series + anime database
- [ ] Multi-provider fallback

---

## Long-term Vision 🚀

**Year 1 (2025):**
- Complete Aniworld integration
- Add 3-4 additional providers
- Build web dashboard
- Implement automatic updates

**Year 2 (2026):**
- Mobile app development
- Multi-site support (additional streaming sites)
- Advanced features (subtitles, quality selection)
- Community features (watchlists, ratings)

**Ultimate Goal:**
- Unified streaming platform for German content
- Self-hosted Netflix-like experience
- Support for series, anime, movies, documentaries
- High reliability and performance

---

## Contributing

Want to help? Pick a task from the TODO list and get started!

**Priority order:**
1. Aniworld Integration (high impact)
2. Multi-Provider Support (reliability)
3. Automatic Updates (maintenance)
4. Web Dashboard (UX improvement)

---

*Last Updated: November 2024*
