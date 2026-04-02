"""Unit tests for mouse_research.searcher module."""
import json
from unittest.mock import patch, MagicMock

import pytest

from mouse_research.searcher import (
    SearchResult,
    call_scraper,
    search_and_filter,
    parse_selection,
    resolve_location,
    LOCATION_CODES,
    ScraperError,
    _parse_scraper_output,
)


# ---------------------------------------------------------------------------
# SearchResult dataclass tests
# ---------------------------------------------------------------------------

class TestSearchResultDataclass:
    def test_searchresult_fields(self):
        r = SearchResult(
            number=1,
            title="York Daily Record",
            date="1982-03-15",
            location="York, PA",
            url="https://www.newspapers.com/image/12345678/",
            keyword_matches=3,
        )
        assert r.number == 1
        assert r.title == "York Daily Record"
        assert r.date == "1982-03-15"
        assert r.location == "York, PA"
        assert r.url == "https://www.newspapers.com/image/12345678/"
        assert r.keyword_matches == 3

    def test_searchresult_has_all_six_fields(self):
        import dataclasses
        fields = {f.name for f in dataclasses.fields(SearchResult)}
        assert fields == {"number", "title", "date", "location", "url", "keyword_matches"}


# ---------------------------------------------------------------------------
# resolve_location tests
# ---------------------------------------------------------------------------

class TestResolveLocation:
    def test_pennsylvania_maps_to_us_pa(self):
        assert resolve_location("Pennsylvania") == "us-pa"

    def test_passthrough_existing_code(self):
        assert resolve_location("us-pa") == "us-pa"

    def test_new_york_maps_to_us_ny(self):
        assert resolve_location("New York") == "us-ny"

    def test_case_insensitive(self):
        assert resolve_location("PENNSYLVANIA") == "us-pa"
        assert resolve_location("new york") == "us-ny"

    def test_whitespace_stripped(self):
        assert resolve_location("  Pennsylvania  ") == "us-pa"

    def test_unknown_location_passthrough(self):
        assert resolve_location("us-ca") == "us-ca"

    def test_location_codes_contains_pennsylvania(self):
        assert "pennsylvania" in LOCATION_CODES
        assert LOCATION_CODES["pennsylvania"] == "us-pa"


# ---------------------------------------------------------------------------
# parse_selection tests
# ---------------------------------------------------------------------------

class TestParseSelection:
    def test_all_returns_full_range(self):
        assert parse_selection("all", 5) == [0, 1, 2, 3, 4]

    def test_single_items(self):
        assert parse_selection("1,3,5", 10) == [0, 2, 4]

    def test_range_and_items(self):
        assert parse_selection("1,3,5-8", 10) == [0, 2, 4, 5, 6, 7]

    def test_zero_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_selection("0", 5)

    def test_out_of_bounds_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_selection("6", 5)

    def test_non_numeric_raises_value_error(self):
        with pytest.raises(ValueError):
            parse_selection("abc", 5)

    def test_all_with_zero_max(self):
        assert parse_selection("all", 0) == []

    def test_single_item_at_max(self):
        assert parse_selection("5", 5) == [4]

    def test_deduplicates_and_sorts(self):
        result = parse_selection("1,1,2", 5)
        assert result == sorted(set(result))

    def test_range_out_of_bounds_raises(self):
        with pytest.raises(ValueError):
            parse_selection("3-10", 5)


# ---------------------------------------------------------------------------
# _parse_scraper_output tests
# ---------------------------------------------------------------------------

class TestParseScraperOutput:
    def test_parses_valid_json_lines(self):
        stdout = json.dumps({"title": "York Daily Record", "pageNumber": 4, "date": "1982-03-15",
                              "location": "York, PA", "keywordMatches": 3,
                              "url": "https://www.newspapers.com/image/12345678/"}) + "\n"
        result = _parse_scraper_output(stdout)
        assert len(result) == 1
        assert result[0]["title"] == "York Daily Record"

    def test_skips_malformed_json_lines(self):
        stdout = "not-json\n" + json.dumps({"title": "Good", "url": "http://example.com"}) + "\n"
        result = _parse_scraper_output(stdout)
        assert len(result) == 1
        assert result[0]["title"] == "Good"

    def test_empty_stdout(self):
        assert _parse_scraper_output("") == []

    def test_multiple_valid_lines(self):
        lines = [
            json.dumps({"title": f"Paper {i}", "url": f"http://example.com/{i}"})
            for i in range(3)
        ]
        result = _parse_scraper_output("\n".join(lines))
        assert len(result) == 3


# ---------------------------------------------------------------------------
# call_scraper tests
# ---------------------------------------------------------------------------

class TestCallScraper:
    def _make_completed_process(self, stdout="", returncode=0, stderr=""):
        mock = MagicMock()
        mock.returncode = returncode
        mock.stdout = stdout
        mock.stderr = stderr
        return mock

    @patch("mouse_research.searcher.subprocess.run")
    def test_calls_node_with_keyword(self, mock_run):
        mock_run.return_value = self._make_completed_process()
        call_scraper("Dave McCollum")
        cmd = mock_run.call_args[0][0]
        assert "node" in cmd[0] or cmd[0].endswith("node")
        assert "--keyword" in cmd
        assert "Dave McCollum" in cmd

    @patch("mouse_research.searcher.subprocess.run")
    def test_includes_scraper_wrapper_js(self, mock_run):
        mock_run.return_value = self._make_completed_process()
        call_scraper("test")
        cmd = mock_run.call_args[0][0]
        assert any("scraper-wrapper.js" in str(arg) for arg in cmd)

    @patch("mouse_research.searcher.subprocess.run")
    def test_years_appended(self, mock_run):
        mock_run.return_value = self._make_completed_process()
        call_scraper("test", years="1975-1985")
        cmd = mock_run.call_args[0][0]
        assert "--years" in cmd
        assert "1975-1985" in cmd

    @patch("mouse_research.searcher.subprocess.run")
    def test_location_appended_after_resolve(self, mock_run):
        mock_run.return_value = self._make_completed_process()
        call_scraper("test", location="Pennsylvania")
        cmd = mock_run.call_args[0][0]
        assert "--location" in cmd
        loc_idx = cmd.index("--location")
        assert cmd[loc_idx + 1] == "us-pa"

    @patch("mouse_research.searcher.subprocess.run")
    def test_max_pages_appended(self, mock_run):
        mock_run.return_value = self._make_completed_process()
        call_scraper("test", max_pages=2)
        cmd = mock_run.call_args[0][0]
        assert "--max-pages" in cmd

    @patch("mouse_research.searcher.subprocess.run")
    def test_nonzero_returncode_raises_scraper_error(self, mock_run):
        mock_run.return_value = self._make_completed_process(returncode=1, stderr="some error")
        with pytest.raises(ScraperError):
            call_scraper("test")

    @patch("mouse_research.searcher.subprocess.run")
    def test_cloudflare_in_stderr_raises_scraper_error_with_login_hint(self, mock_run):
        mock_run.return_value = self._make_completed_process(
            returncode=1, stderr="Cloudflare blocked the request"
        )
        with pytest.raises(ScraperError, match="Session may have expired"):
            call_scraper("test")

    @patch("mouse_research.searcher.subprocess.run")
    def test_timeout_set_to_300(self, mock_run):
        mock_run.return_value = self._make_completed_process()
        call_scraper("test")
        kwargs = mock_run.call_args[1]
        assert kwargs.get("timeout") == 300

    @patch("mouse_research.searcher.subprocess.run")
    def test_invalid_years_format_raises_value_error(self, mock_run):
        with pytest.raises(ValueError):
            call_scraper("test", years="bad-years")

    @patch("mouse_research.searcher.subprocess.run")
    def test_returns_list_of_dicts(self, mock_run):
        stdout = json.dumps({"title": "Paper", "url": "http://ex.com", "date": "1980-01-01",
                             "location": "PA", "keywordMatches": 1}) + "\n"
        mock_run.return_value = self._make_completed_process(stdout=stdout)
        result = call_scraper("test")
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)


# ---------------------------------------------------------------------------
# search_and_filter tests
# ---------------------------------------------------------------------------

class TestSearchAndFilter:
    def _make_config(self, vault_path="/tmp/vault"):
        config = MagicMock()
        config.vault.path = vault_path
        return config

    def _raw_results(self):
        return [
            {"title": "Paper A", "date": "1980-01-01", "location": "York, PA",
             "url": "https://www.newspapers.com/image/111/", "keywordMatches": 2},
            {"title": "Paper B", "date": "1981-02-02", "location": "York, PA",
             "url": "https://www.newspapers.com/image/222/", "keywordMatches": 1},
            {"title": "Paper C", "date": "1982-03-03", "location": "York, PA",
             "url": "https://www.newspapers.com/image/333/", "keywordMatches": 5},
        ]

    @patch("mouse_research.searcher.is_duplicate")
    @patch("mouse_research.searcher.call_scraper")
    def test_filters_duplicates_and_returns_count(self, mock_scraper, mock_is_dup):
        mock_scraper.return_value = self._raw_results()
        # URL /222/ is a duplicate
        mock_is_dup.side_effect = lambda vault, url: "222" in url
        config = self._make_config()
        results, excluded = search_and_filter("test", None, None, config)
        assert excluded == 1
        assert len(results) == 2
        assert all(isinstance(r, SearchResult) for r in results)

    @patch("mouse_research.searcher.is_duplicate")
    @patch("mouse_research.searcher.call_scraper")
    def test_results_have_1based_numbering(self, mock_scraper, mock_is_dup):
        mock_scraper.return_value = self._raw_results()
        mock_is_dup.return_value = False
        config = self._make_config()
        results, _ = search_and_filter("test", None, None, config)
        assert [r.number for r in results] == [1, 2, 3]

    @patch("mouse_research.searcher.is_duplicate")
    @patch("mouse_research.searcher.call_scraper")
    def test_maps_keyword_matches_field(self, mock_scraper, mock_is_dup):
        mock_scraper.return_value = self._raw_results()
        mock_is_dup.return_value = False
        config = self._make_config()
        results, _ = search_and_filter("test", None, None, config)
        assert results[0].keyword_matches == 2
        assert results[2].keyword_matches == 5

    @patch("mouse_research.searcher.is_duplicate")
    @patch("mouse_research.searcher.call_scraper")
    def test_no_duplicates_returns_all(self, mock_scraper, mock_is_dup):
        mock_scraper.return_value = self._raw_results()
        mock_is_dup.return_value = False
        config = self._make_config()
        results, excluded = search_and_filter("test", None, None, config)
        assert excluded == 0
        assert len(results) == 3

    @patch("mouse_research.searcher.is_duplicate")
    @patch("mouse_research.searcher.call_scraper")
    def test_all_duplicates_returns_empty(self, mock_scraper, mock_is_dup):
        mock_scraper.return_value = self._raw_results()
        mock_is_dup.return_value = True
        config = self._make_config()
        results, excluded = search_and_filter("test", None, None, config)
        assert excluded == 3
        assert results == []
