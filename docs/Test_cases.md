# PC Upgrade Advisor Test Cases

| ID | Area | Scenario and test data | Expected result | Status |
|---|---|---|---|---|
| TC-01 | Advisor | Submit a known CPU, GPU, and motherboard with matching sockets, 16 GB RAM, NVMe storage, 1080p, gaming, and sufficient PSU | Results page is returned; compatibility is positive; no false upgrade verdict is shown | PASS |
| TC-02 | Advisor | Submit a CPU name, GPU name, or motherboard name that is not in the database | HTTP 400 page identifies every missing component and provides a retry link | PASS |
| TC-03 | Compatibility | Use CPU socket AM4 with motherboard socket LGA1700 | Analysis is blocked from upgrade recommendations and the result lists a socket mismatch | PASS |
| TC-04 | Compatibility | Use matching sockets but a PSU below CPU TDP + GPU TDP + 150 W | Hardware remains socket-compatible; PSU warning shows the calculated minimum wattage | PASS |
| TC-05 | Bottleneck | Use CPU score 50 and GPU score 100 | Result reports CPU Bottleneck and 50.0 percent | PASS |
| TC-06 | Bottleneck | Use CPU score 200 and GPU score 100 | Result reports GPU Bottleneck and 50.0 percent | PASS |
| TC-07 | Upgrade decision | Use HDD storage and 8 GB RAM for gaming | Verdict is UPGRADE REQUIRED and includes storage and RAM reasons | PASS |
| TC-08 | Upgrade decision | Use 16 GB RAM for AI workload | Result includes guidance to use at least 32 GB RAM | PASS |
| TC-09 | Recommendations | Use SATA SSD, editing workload, and RAM below 32 GB | Recommendations include an NVMe Gen 4 drive and a 32 GB RAM target | PASS |
| TC-10 | Recommendations | Candidate GPU has no price in the database | GPU can still be recommended; UI labels price unavailable and marks the total incomplete | PASS |
| TC-11 | Budget | Set a positive budget below the known recommendation price | Results show the known total exceeds the budget; no alternative card is silently treated as purchased together | PASS |
| TC-12 | Registration | Submit username shorter than 3 characters or password shorter than 8 characters | HTTP 400 response renders the form with the specific validation message | PASS |
| TC-13 | Registration | Register a new user, then submit the same username or email again with different casing | First request redirects to home and creates a session; second request returns HTTP 400 with duplicate-account error | PASS |
| TC-14 | Login | Submit a valid username and password | Request redirects to home and session contains user ID and username | PASS |
| TC-15 | Login | Submit an unknown username or incorrect password | HTTP 401 response renders the generic invalid-credentials message | PASS |
| TC-16 | History access | Request `/history` without a logged-in session | Request redirects to `/login` | PASS |
| TC-17 | History isolation | Logged-in user requests another user's analysis ID | Request redirects to that user's own history and does not expose the record | PASS |
| TC-18 | History recovery | Open a saved analysis with malformed or missing result JSON | Missing JSON returns the unavailable-result view with an appropriate 404/500 response | PASS |
| TC-19 | Password recovery | Submit an unknown email | Same generic success message is shown and no token is created | PASS |
| TC-20 | Password recovery | Submit a valid email twice | Earlier unused token is invalidated; only the newest token remains usable | PASS |
| TC-21 | Password reset | Submit an expired, used, or unknown token | Reset is rejected with an error and the password is unchanged | PASS |
| TC-22 | Password reset | Submit a valid token with passwords shorter than 8 characters or with mismatched confirmation | Reset is rejected with a clear validation message | PASS |
| TC-23 | Password reset | Submit a valid token and matching password, then reuse the same token | First request succeeds and logs the user in; second request is rejected | PASS |