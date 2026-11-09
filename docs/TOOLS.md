# Echo's toolbox — 605 tools

Echo's AI picks these by itself when you ask for something ("what's the EMI on…", "find big files in Downloads", "is GitHub down").
With this many tools, Echo shows the AI only the ~30 that best match your request, and the AI can search for more with `toolbox.find`.

- ⚠ = changes something, so Echo asks you first · 🌐 = uses the internet · 📱 = needs the Echo app running (lists, memories, timers)
- Other AI apps can use them too: `py -3.12 desktop\EchoDesktop\echo_tools_mcp.py` is an MCP server (`claude mcp add -s user echo-tools -- py -3.12 <full path to echo_tools_mcp.py>`).

| Area | Tools |
|---|---|
| Maths, statistics, numbers, randomness | 48 |
| Unit conversions | 16 |
| Money, loans, savings, tax, prices | 37 |
| Dates, times, time zones, calendars | 28 |
| Text tools: counts, cases, find/replace, regex, ciphers | 55 |
| Encodings, hashes, ids, passwords, tokens | 36 |
| JSON, CSV, XML, URLs, colours, formats | 45 |
| Files and folders on this PC | 34 |
| This PC: hardware, processes, network, settings | 42 |
| Control the PC: keys, typing, mouse, windows, apps | 24 |
| Live information from the internet | 88 |
| Health, home, cooking, travel calculators | 18 |
| India: PAN, GSTIN, IFSC, PIN codes, lakh/crore | 10 |
| Developer tools: git, code stats, templates, HTTP | 31 |
| Your lists, notes, memories, timers, messages | 15 |
| Moltbook, the social network for AI agents: read, search, and (with your OK) post | 14 |
| Watches, reports, comparisons, trends and dashboards on any data; the 1,000 automation ideas; briefings | 31 |
| Your personal assistant: tasks and due dates, plan my day, follow-ups, people and birthdays, habits, expenses and budgets, journal, focus sessions, meeting notes, my day, weekly review, taught phrases | 33 |

## Maths, statistics, numbers, randomness (48)

- `calculate(expression:string)` — Calculate a maths expression (+ - * / ^, %, sqrt, brackets, 'x% of y').
- `cgpa_to_percentage(cgpa:number, scale?:cbse|x10|us_4)` — Convert CGPA to a percentage (CBSE: × 9.5; plain ×10; or US 4-point to an approximate %).
- `combinations(n:integer, r:integer)` — Ways to choose r of n: combinations (order doesn't matter) and permutations (order matters).
- `convert_base(value:string, from_base:integer, to_base:integer)` — Convert a whole number between bases 2–36.
- `decimal_to_fraction(value:number, max_denominator?:integer)` — Closest simple fraction for a decimal.
- `factorial(n:integer)` — n! (n factorial).
- `factors(n:integer)` — All divisors of a whole number.
- `fibonacci(n:integer)` — The first n Fibonacci numbers.
- `flip_coin(times?:integer)` — Flip a coin.
- `format_number(value:number, style?:international|indian|compact, places?:integer)` — Format a number with separators (12,345,678 / 1,23,45,678) or compactly (12.3M).
- `fraction_to_decimal(fraction:string)` — Fraction (like 3/8 or 1 1/2) to a decimal.
- `from_roman(roman:string)` — Roman numerals to a number.
- `gcd(numbers:array)` — Greatest common divisor (HCF) of whole numbers.
- `is_prime(n:integer)` — Is a whole number prime?
- `lcm(numbers:array)` — Least common multiple of whole numbers.
- `linear_regression(x:array, y:array)` — Best-fit line y = a·x + b and the correlation of two lists.
- `list_permutations(items:array, limit?:integer)` — All orderings of a few items (up to 7).
- `logarithm(value:number, base?:number)` — Logarithm of a number (base 10 by default; use 2.718281828 for natural log).
- `marks_percentage(marks:array, out_of:array)` — Total marks and percentage from marks and maximums.
- `matrix_determinant(matrix:array)` — Determinant of a square matrix (up to 6×6).
- `matrix_multiply(a:array, b:array)` — Multiply two matrices.
- `nth_root(value:number, n?:number)` — The n-th root (2 = square root, 3 = cube root).
- `number_properties(n:integer)` — Interesting facts about a whole number: even/odd, prime, square, cube, perfect, digit sum, binary.
- `number_to_words(n:integer, system?:international|indian)` — Write a whole number in words (international: million; indian: lakh, crore).
- `percent_change(old:number, new:number)` — Percentage increase or decrease from an old value to a new one.
- `percent_of(percent:number, value:number)` — What is P percent of a number.
- `point_distance(a:array, b:array)` — Straight-line distance between two points (2D or 3D).
- `power(base:number, exponent:number)` — base raised to exponent.
- `prime_factors(n:integer)` — Prime factorisation of a whole number.
- `random_choice(options:array, count?:integer)` — Pick at random from a list of options.
- `random_number(low?:integer, high?:integer, count?:integer)` — Random whole number(s) between low and high (inclusive).
- `rescale(value:number, low:number, high:number, new_low:number, new_high:number)` — Map a value from one range to another (e.g. a score out of 37 to a percentage).
- `roll_dice(dice?:integer, sides?:integer)` — Roll one or more dice (any number of sides).
- `round_number(value:number, places?:integer)` — Round a number to some decimal places.
- `scientific_notation(value:number, digits?:integer)` — Write a number in scientific notation.
- `shape_area(shape:circle|square|rectangle|triangle|trapezium|ellipse|sphere|cylinder, a:number, b?:number, c?:number)` — Area/perimeter (2D) or volume/surface (3D). circle a=radius; rectangle a,b; triangle a=base b=height; trapezium a,b parallel sides c=height; ellipse a,b semi-axes; sphere a=radius; cylinder/cone a=radius b=height; cube a=side.
- `shuffle_list(items:array)` — Shuffle a list into random order.
- `simplify_ratio(a:integer, b:integer)` — Simplify a ratio like 1920:1080 to 16:9.
- `solve_linear_2x2(a1:number, b1:number, c1:number, a2:number, b2:number, c2:number)` — Solve a1·x + b1·y = c1 and a2·x + b2·y = c2.
- `solve_quadratic(a:number, b:number, c:number)` — Solve a·x² + b·x + c = 0.
- `split_by_percent(amount:number, percents:array)` — Split an amount by percentages (e.g. a 50/30/20 budget).
- `split_into_teams(people:array, teams?:integer)` — Split people randomly into balanced teams.
- `statistics_summary(numbers:array)` — Count, sum, mean, median, mode, min, max, range, standard deviation and quartiles of numbers.
- `to_roman(n:integer)` — Whole number (1–3999) to Roman numerals.
- `trig(function:sin|cos|tan|asin|acos|atan, angle:number, degrees?:boolean)` — Trigonometry in degrees (or radians). For asin/acos/atan, 'angle' is the ratio and the answer is an angle.
- `weighted_average(numbers:array, weights:array)` — Weighted average of numbers.
- `what_percent(part:number, whole:number)` — What percent one number is of another.
- `words_to_number(words:string)` — Turn a number in words ('two lakh fifty thousand') into digits.

## Unit conversions (16)

- `convert_angle(value:number, from_unit:string, to_unit:string)` — Convert angles (degree, radian, gradian, turn).
- `convert_area(value:number, from_unit:string, to_unit:string)` — Convert area/land (sq m, sq km, sq ft, sq yd, acre, hectare, sq mile, cent, guntha, bigha (UP)).
- `convert_data_size(value:number, from_unit:string, to_unit:string)` — Convert data sizes (bit, byte, kb, mb, gb, tb, kib, mib, gib, tib).
- `convert_duration(value:number, from_unit:string, to_unit:string)` — Convert time spans (second, minute, hour, day, week, month, year, millisecond).
- `convert_energy(value:number, from_unit:string, to_unit:string)` — Convert energy (joule, kj, calorie, kcal, wh, kwh, btu, ev).
- `convert_fuel_economy(value:number, from_unit:string, to_unit:string)` — Convert fuel economy between km/l, l/100km, mpg (US) and mpg (UK).
- `convert_length(value:number, from_unit:string, to_unit:string)` — Convert length/distance (mm, cm, m, km, inch, foot, yard, mile, nautical mile, micrometre).
- `convert_power(value:number, from_unit:string, to_unit:string)` — Convert power (w, kw, hp, ton (ac), btu/h).
- `convert_pressure(value:number, from_unit:string, to_unit:string)` — Convert pressure (pa, kpa, bar, atm, psi, mmhg).
- `convert_speed(value:number, from_unit:string, to_unit:string)` — Convert speed (m/s, km/h, mph, knot, ft/s).
- `convert_temperature(value:number, from_unit:string, to_unit:string)` — Convert temperatures between Celsius, Fahrenheit and Kelvin.
- `convert_volume(value:number, from_unit:string, to_unit:string)` — Convert volume/liquid (ml, l, m3, tsp, tbsp, cup, fl oz, pint, gallon, uk gallon).
- `convert_weight(value:number, from_unit:string, to_unit:string)` — Convert weight/mass (mg, g, kg, tonne, lb, oz, stone, quintal, tola, carat).
- `cups_to_grams(amount:number, unit:string, ingredient:string)` — Kitchen conversion: cups / tablespoons / teaspoons of an ingredient to grams (or grams to cups).
- `oven_temperature(value:number, from_unit?:string)` — Oven temperature in °C, °F and gas mark.
- `shoe_size(size:number, system?:string)` — Adult shoe size across EU, UK/India, US (men's) and foot length in cm (approximate).

## Money, loans, savings, tax, prices (37)

- `appliance_running_cost(watts:number, hours_per_day:number, rate_per_unit:number, days?:integer)` — What an appliance costs to run (e.g. a 1.5 kW AC for 8 hours a day).
- `break_even(fixed_costs:number, price:number, variable_cost:number)` — Units you must sell to break even.
- `cagr(start:number, end:number, years:number)` — Compound annual growth rate between two values.
- `compare_loans(principal:number, rate_a:number, years_a:number, rate_b:number, years_b:number)` — Compare two loan offers by EMI and total interest.
- `compare_unit_price(price_a:number, qty_a:number, price_b:number, qty_b:number)` — Which pack is better value (price per unit).
- `compound_interest(principal:number, annual_rate:number, years:number, per_year?:integer)` — Compound interest: final amount and interest earned (per_year = compounding times a year, 4 = quarterly).
- 🌐 `convert_currency(amount:number, from_currency:string, to_currency:string)` — Convert money between currencies at today's rate (live).
- 🌐 `crypto_price(coin:string)` — Live price of a cryptocurrency in USD and INR.
- `discount(price:number, percent:number, extra_percent?:number)` — Price after a discount (and an optional extra discount on top).
- `electricity_cost(units:number, rate_per_unit:number, fixed_charge?:number)` — Estimate an electricity bill from units (kWh) used and your tariff.
- `emergency_fund(monthly_expenses:number, months?:integer)` — How big an emergency fund should be (usually 3–6 months of expenses).
- 🌐 `exchange_rates(base?:string, currencies?:array)` — Today's exchange rates from one currency to many (live).
- `fd_maturity(principal:number, annual_rate:number, years:number)` — Fixed deposit maturity (quarterly compounding, as most Indian banks use).
- `gratuity(last_basic_plus_da:number, years:number)` — Gratuity under India's Payment of Gratuity Act (15 days' pay per year of service; 5+ years usually needed).
- `gst_add(price:number, rate?:number)` — Add GST to a price (rates 0, 5, 12, 18, 28…).
- `gst_remove(price:number, rate?:number)` — Split a GST-inclusive price into base price and GST.
- `inflation_adjust(amount:number, inflation:number, years:number)` — Future cost of something today, and today's value of money in the future.
- `loan_emi(principal:number, annual_rate:number, years:number)` — Monthly EMI, total interest and total paid for a loan.
- `loan_schedule(principal:number, annual_rate:number, years:number)` — Year-by-year loan schedule: principal and interest paid, balance left.
- `loan_tenure(principal:number, annual_rate:number, emi:number)` — How long it takes to repay a loan with a given monthly EMI.
- `lumpsum_future_value(amount:number, annual_return:number, years:number)` — What a one-time investment grows to.
- `margin_markup(cost:number, price:number)` — Profit, margin (on price) and markup (on cost).
- `price_for_margin(cost:number, margin_percent:number)` — Selling price that gives a target margin.
- `rd_maturity(monthly:number, annual_rate:number, months:integer)` — Recurring deposit maturity (quarterly compounding).
- `retirement_corpus(current_age:integer, retire_age:integer, monthly_expenses_today:number, inflation?:number, years_after?:integer, return_after?:number)` — Rough retirement corpus needed (expenses grown by inflation, drawn down over years_after).
- `roi(cost:number, gain:number)` — Return on investment.
- `salary_breakdown(amount:number, period?:hour|day|month|year, hours_per_week?:number)` — Convert pay between hourly, daily, monthly and yearly (gross, before tax).
- `salary_hike(current:number, hike_percent:number)` — New salary after a percentage hike.
- `savings_goal_time(goal:number, monthly:number, annual_return?:number, already_saved?:number)` — How many months to reach a savings goal.
- `simple_interest(principal:number, annual_rate:number, years:number)` — Simple interest and final amount.
- `sip_future_value(monthly:number, annual_return:number, years:number)` — What a monthly SIP grows to (expected return, compounded monthly, paid at the start of each month).
- `sip_needed_for_goal(goal:number, annual_return:number, years:number)` — Monthly SIP needed to reach a goal amount.
- `split_bill(total:number, people:integer, already_paid?:array)` — Split a bill evenly; with already_paid (one amount per person) it says who owes whom.
- `tip(bill:number, percent?:number, people?:integer)` — Tip and per-person share.
- 🌐 `top_cryptos(count?:integer)` — Top cryptocurrencies by market cap (live).
- `trip_fuel_cost(distance_km:number, mileage_kmpl:number, fuel_price:number, people?:integer)` — Fuel needed and cost for a trip.
- `yearly_deposit_maturity(yearly:number, annual_rate:number, years?:integer)` — Maturity of a yearly deposit like PPF (deposited at the start of each year, compounded yearly).

## Dates, times, time zones, calendars (28)

- `add_to_date(start?:string, days?:integer, weeks?:integer, months?:integer, years?:integer)` — A date plus or minus days, weeks, months or years.
- `age(birth_date:string, on_date?:string)` — Exact age from a birth date, and days to the next birthday.
- `bedtime_for(wake_time:string)` — Good bedtimes for waking at a time (90-minute sleep cycles, 15 minutes to fall asleep).
- `business_days(start:string, end:string, holidays?:array)` — Working days (Mon–Fri) between two dates, inclusive, minus any holidays you list.
- `clock_12_24(time_text:string)` — Convert a time between 12-hour and 24-hour clocks.
- `convert_time_zone(time_text:string, from_place:string, to_place:string, on_date?:string)` — Convert a clock time from one city/zone to another.
- `countdown(event:string)` — Time left until a date (or date and time, '2026-12-31 23:59').
- `date_difference(start:string, end?:string)` — Days (and weeks, months) between two dates.
- `date_to_unix(day:string, time_text?:string)` — A local date and time to a Unix timestamp.
- `financial_year(day?:string)` — Indian financial year (April–March) and quarter for a date, plus the calendar quarter.
- `format_duration(seconds:number)` — Turn seconds into days, hours, minutes and seconds.
- `holiday_date(name:string, year?:integer)` — Next date of a fixed or rule-based holiday (Christmas, Easter, Republic Day, Mother's Day, Thanksgiving…). Lunar festivals like Diwali or Eid change yearly: look those up with web tools.
- `hours_between(start:string, end:string, break_minutes?:integer)` — Hours and minutes between two clock times (overnight works), minus a break.
- `leap_year(year:integer)` — Is a year a leap year?
- `meeting_overlap(places:array, start_hour?:integer, end_hour?:integer)` — Hours (in the first place's time) when everyone is within working hours today.
- `month_calendar(year?:integer, month?:integer)` — A month's calendar as text (defaults to this month).
- `moon_phase(day?:string)` — Moon phase on a date.
- `next_weekday(weekday:string, after?:string)` — Date of the next given weekday.
- `nth_weekday_of_month(year:integer, month:integer, weekday:string, nth?:integer)` — The n-th (or last, nth=-1) given weekday of a month.
- `repeating_dates(start:string, every_days:integer, count?:integer)` — A list of dates repeating every N days (refills, payments, cycles).
- `time_difference(place_a:string, place_b:string)` — How many hours one place is ahead of another right now.
- `time_in(place:string)` — Current local time in a city, country or time zone.
- `unix_to_date(timestamp:number, place?:string)` — Unix timestamp (seconds or milliseconds) to a readable date, in UTC and your time or a city's.
- `wake_times_for(bed_time:string)` — Good wake-up times if you go to bed at a time (90-minute cycles).
- `week_number(day?:string)` — ISO week number and day of the year for a date.
- `weekday_of(day:string)` — Which day of the week a date falls on.
- `world_clock(places:array)` — The time now in several places at once.
- `zodiac_sign(birth_date:string)` — Western zodiac sign and Chinese zodiac animal for a birth date.

## Text tools: counts, cases, find/replace, regex, ciphers (55)

- `binary_to_text(binary:string)` — Binary (8-bit groups) back to text.
- `caesar_cipher(text:string, shift?:integer, decode?:boolean)` — Caesar cipher (shift 13 = ROT13). For fun, not security.
- `censor_words(text:string, words:array, mask?:string)` — Mask chosen words in a text.
- `change_case(text:string, style:upper|lower|title|sentence|camel|pascal|snake|kebab)` — Change the case of text.
- `character_info(text:string)` — Unicode name and code point of each character (up to 40).
- `clean_whitespace(text:string)` — Collapse extra spaces and blank lines, trim each line.
- `closest_matches(word:string, options:array, count?:integer)` — The options closest in spelling to a word.
- `count_occurrences(text:string, character:string, ignore_case?:boolean)` — How many times a letter, word or phrase appears.
- `extract_dates(text:string)` — Find dates written in a text.
- `extract_emails(text:string)` — Pull out every email address.
- `extract_hashtags(text:string)` — Pull out #hashtags and @mentions.
- `extract_links(text:string)` — Pull out every web link.
- `extract_numbers(text:string)` — Pull out the numbers (commas understood).
- `extract_phone_numbers(text:string)` — Pull out phone numbers.
- `find_emoji(query:string, limit?:integer)` — Find emoji and symbols by name ('heart', 'rupee', 'arrow').
- `find_replace(text:string, find:string, replace:string, ignore_case?:boolean, whole_word?:boolean)` — Find and replace in text (plain text, not regex).
- `from_morse(morse:string)` — Morse code to text.
- `html_to_text(text:string)` — HTML to plain text.
- `is_anagram(a:string, b:string)` — Are two words or phrases anagrams of each other?
- `is_palindrome(text:string)` — Does text read the same backwards (ignoring spaces and punctuation)?
- `is_pangram(text:string)` — Does text use every letter of the alphabet? Lists missing letters.
- `join_items(items:array, separator?:string)` — Join pieces into one line with a separator.
- `key_sentences(text:string, count?:integer)` — The most important sentences of a text (by word frequency; no AI needed).
- `letter_breakdown(text:string)` — Letters, vowels, consonants, digits, spaces and symbols in text.
- `lorem_ipsum(words?:integer)` — Placeholder text.
- `make_acronym(text:string)` — Make an acronym from a phrase.
- `make_list(text:string, style?:bullets|numbered|checklist|comma)` — Turn lines into a bulleted, numbered, checklist or comma-separated list.
- `markdown_to_text(text:string)` — Markdown to plain text.
- `nato_spelling(text:string)` — Spell text with the NATO phonetic alphabet (Alfa, Bravo…).
- `number_lines(text:string, start?:integer)` — Add line numbers.
- `pad_text(text:string, width:integer, align?:left|right|center, fill?:string)` — Pad text to a width (left, right or centre).
- `pig_latin(text:string)` — Translate into Pig Latin (a word game).
- `readability(text:string)` — Flesch reading ease and grade level (how easy a text is to read).
- `redact_personal_info(text:string)` — Mask emails, phone numbers, card numbers, Aadhaar-like and PAN-like numbers before sharing text.
- `regex_replace(pattern:string, replace:string, text:string, ignore_case?:boolean)` — Replace using a regular expression (\1 for groups).
- `regex_test(pattern:string, text:string, ignore_case?:boolean)` — Test a regular expression: matches, positions and groups.
- `remove_accents(text:string)` — Remove accents (café → cafe).
- `remove_duplicate_lines(text:string, ignore_case?:boolean)` — Remove repeated lines, keeping the first of each.
- `remove_line_breaks(text:string, keep_paragraphs?:boolean)` — Join lines broken in the middle of sentences (e.g. text copied from a PDF).
- `remove_punctuation(text:string)` — Remove punctuation.
- `repeat_text(text:string, times:integer, separator?:string)` — Repeat text a number of times.
- `reverse_text(text:string, by?:characters|words|lines)` — Reverse text by characters, words or lines.
- `slugify(text:string)` — Make a URL slug ('hello-world-10-tips').
- `sort_lines(text:string, order?:a-z|z-a|number|length, unique?:boolean)` — Sort lines (A–Z, Z–A, by number or length), optionally removing duplicates.
- `split_text(text:string, separator?:string)` — Split text into pieces by a separator.
- `straighten_quotes(text:string)` — Curly quotes, long dashes and ellipses to plain ASCII.
- `text_diff(old:string, new:string)` — Show what changed between two texts (line by line, or word by word for one-liners).
- `text_similarity(a:string, b:string)` — How similar two texts are (0–100%).
- `text_stats(text:string)` — Words, characters, sentences, paragraphs, lines and reading/speaking time of a text.
- `text_table(rows:array)` — Line up rows into a neat text table.
- `text_to_binary(text:string)` — Text to binary (UTF-8 bytes).
- `to_morse(text:string)` — Text to Morse code (/ between words).
- `truncate(text:string, length?:integer, ellipsis?:string)` — Shorten text to a length at a word boundary.
- `word_frequency(text:string, top?:integer, skip_common?:boolean)` — Most common words (common words like 'the' skipped).
- `wrap_text(text:string, width?:integer)` — Wrap text to a line width.

## Encodings, hashes, ids, passwords, tokens (36)

- `all_hashes(text:string)` — Every common hash of a text at once.
- `base32_decode(data:string)` — Decode Base32 to text.
- `base32_encode(text:string)` — Base32-encode text.
- `base64_decode(data:string)` — Decode Base64 (normal or URL-safe) to text.
- `base64_encode(text:string, url_safe?:boolean)` — Base64-encode text (UTF-8).
- `crc32_checksum(text:string)` — CRC-32 and Adler-32 checksums of text.
- `gzip_compress(text:string)` — Gzip-compress text and give it back as Base64.
- `gzip_decompress(data:string)` — Decompress Base64 gzip data back to text.
- `hash_text(text:string, algorithm?:md5|sha1|sha224|sha256|sha384|sha512|sha3_256|sha3_512)` — Hash text (UTF-8) with MD5, SHA-1, SHA-2, SHA-3 or BLAKE2.
- `hex_decode(data:string)` — Hexadecimal bytes to text.
- `hex_encode(text:string)` — Text to hexadecimal bytes.
- `hmac_sign(key:string, message:string, algorithm?:sha256|sha1|sha512|md5)` — HMAC signature of a message with a key (as used by webhooks).
- `html_escape(text:string)` — Escape text for HTML (& < > ").
- `html_unescape(text:string)` — Turn HTML entities back into characters.
- `inspect_uuid(value:string)` — Check a UUID and say its version.
- `json_escape(text:string)` — Escape text as a JSON string literal.
- `json_unescape(text:string)` — Unescape a JSON string literal (with or without the outer quotes).
- `jwt_decode(token:string)` — Read a JWT's header and claims (signature not verified).
- `jwt_sign(claims:object, secret:string, expires_minutes?:integer)` — Create an HS256-signed JWT (for testing your own apps).
- `make_passphrase(words?:integer, separator?:string)` — A memorable passphrase of random words.
- `make_password(length?:integer, symbols?:boolean, avoid_lookalikes?:boolean)` — A strong random password (returned to you only; not stored).
- `make_short_id(length?:integer)` — Short random URL-safe id (like NanoID).
- `make_ulid()` — New ULID (sortable by time, 26 characters).
- `make_uuid(count?:integer, uppercase?:boolean)` — New random UUIDs (version 4).
- `password_strength(password:string)` — How strong a password is (estimated guessing effort). It isn't sent or stored anywhere.
- `punycode(domain:string, decode?:boolean)` — Convert an international domain name to/from punycode (xn--…).
- `quoted_printable(text:string, decode?:boolean)` — Quoted-printable encoding (used in emails).
- `random_pin(length?:integer)` — Random numeric PIN or code.
- `random_token(bytes_count?:integer, style?:hex|urlsafe|base64)` — Cryptographically random token.
- `rot47(text:string)` — ROT47 (shifts all printable ASCII; applying it twice gives the original).
- `to_braille(text:string)` — Text to Grade-1 Unicode braille (letters and digits).
- `totp_code(secret:string, digits?:integer, period?:integer)` — Current 2FA (TOTP) code for a Base32 secret, like an authenticator app.
- `unicode_escape(text:string, decode?:boolean)` — Write non-ASCII characters as \uXXXX escapes (or decode them).
- `url_decode(text:string)` — Decode percent-encoded URL text (+ as space too).
- `url_encode(text:string, keep_slashes?:boolean)` — Percent-encode text for a URL.
- `uuid_from_name(name:string, namespace?:dns|url|oid|x500)` — Deterministic UUID (version 5) from a name — the same name always gives the same id.

## JSON, CSV, XML, URLs, colours, formats (45)

- `chmod_calculate(owner?:string, group?:string, others?:string)` — Permission letters (r, w, x) to a chmod number.
- `chmod_explain(mode:integer)` — Explain Unix file permissions like 755 or 644.
- `clean_url_tracking(url:string)` — Remove tracking parameters (utm_, fbclid, gclid…) from a link.
- `color_contrast(foreground:string, background:string)` — WCAG contrast ratio of two colours and whether text is readable.
- `color_convert(value:string)` — Convert a colour between hex, RGB and HSL ('#1e90ff', 'rgb(30,144,255)', 'hsl(210,100%,56%)').
- `color_palette(value:string)` — Matching colours: complementary, analogous, triadic, and lighter/darker shades.
- `cron_explain(schedule:string)` — Explain a 5-part cron schedule in words.
- `cron_next_runs(schedule:string, count?:integer)` — The next times a cron schedule will run (local time).
- `csv_column_counts(text:string, column:string)` — How often each value appears in a CSV column.
- `csv_filter(text:string, column:string, value:string, contains?:boolean)` — Keep only CSV rows where a column equals (or contains) a value.
- `csv_sort(text:string, column:string, descending?:boolean)` — Sort CSV rows by a column (numbers sort as numbers).
- `csv_summary(text:string)` — Rows, columns, and for number columns: sum, average, min and max.
- `csv_to_json(text:string)` — CSV (with a header row) to a JSON array of objects.
- `csv_to_markdown(text:string)` — CSV to a Markdown table.
- `csv_to_sql(text:string, table:string)` — CREATE TABLE and INSERT statements from CSV (types guessed).
- `email_check(email:string)` — Check an email address's format (not whether the mailbox exists).
- `env_file_to_json(text:string, hide_values?:boolean)` — Read a .env file's variable names (values hidden unless hide_values is false).
- `http_status_meaning(code:integer)` — What an HTTP status code means.
- `human_size(size_bytes:number)` — Bytes to a readable size (KB, MB, GB).
- `ini_to_json(text:string)` — Read an INI/config file as JSON.
- `ip_address_info(address:string)` — What kind of IP address this is (private, public, loopback…).
- `ip_in_network(address:string, network:string)` — Is an IP address inside a network range?
- `json_diff(old:string, new:string)` — Differences between two JSON documents.
- `json_flatten(text:string)` — Flatten nested JSON into dotted keys.
- `json_format(text:string, indent?:integer, sort_keys?:boolean)` — Pretty-print JSON.
- `json_get(text:string, path:string)` — Get a value from JSON by path, like user.names[1] or items.price (lists map over items).
- `json_minify(text:string)` — Minify JSON to one line.
- `json_schema_from_example(text:string)` — Make a JSON Schema from an example JSON value.
- `json_structure(text:string)` — Outline of a JSON document's structure (keys and types).
- `json_to_csv(text:string)` — JSON array of objects to CSV.
- `json_validate(text:string)` — Is this valid JSON? Points at the error if not.
- `markdown_table_to_csv(text:string)` — Markdown table to CSV.
- `mime_type(name:string)` — MIME type for a file name or extension (and extensions for a MIME type like image/png).
- `port_meaning(port:integer)` — What usually runs on a network port.
- `query_string_parse(query:string)` — Parse a query string (repeated keys become lists).
- `sql_format(sql:string)` — Tidy an SQL query: keywords in capitals, one clause per line.
- `subnet_info(network:string)` — Subnet calculator: netmask, usable hosts, range, broadcast.
- `toml_to_json(text:string)` — Read TOML (pyproject.toml, Cargo.toml…) as JSON.
- `url_build(base:string, params:object)` — Build a URL with query parameters (properly encoded).
- `url_parse(url:string)` — Split a URL into scheme, host, port, path, query parameters and fragment.
- `version_bump(version:string, part?:major|minor|patch)` — Next version number (major/minor/patch bump).
- `version_compare(a:string, b:string)` — Compare two version numbers.
- `xml_find(text:string, path:string)` — Find elements in XML with an ElementTree path (like .//item or ./book/title).
- `xml_format(text:string)` — Pretty-print XML.
- `xml_to_json(text:string)` — XML to JSON.

## Files and folders on this PC (34)

- ⚠ `append_to_file(path:string, content:string)` — Add text to the end of a text file. Asks first.
- ⚠ `batch_rename(folder:string, pattern:string, prefix:string, start?:integer)` — Rename every file matching a pattern to prefix_001, prefix_002… (keeping extensions). Asks first.
- `compare_files(path_a:string, path_b:string)` — Are two files identical? For text files, shows what differs.
- ⚠ `copy_file(source:string, destination:string)` — Copy a file or folder. Asks first.
- `count_file_lines(path:string)` — Lines, words and characters in a text file.
- ⚠ `create_folder(path:string)` — Create a folder. Asks first.
- ⚠ `delete_to_recycle_bin(path:string)` — Move a file or folder to the Recycle Bin (you can restore it). Asks first.
- `drives_free_space()` — Every drive with free and total space.
- `file_info(path:string)` — Size, dates and type of a file or folder.
- `file_types_summary(folder?:string)` — How many files of each type a folder has, and their total size.
- `find_duplicate_files(folder?:string, min_size_kb?:integer)` — Groups of identical files (same content) under a folder.
- `find_files(name:string, folder?:string, limit?:integer)` — Find files by name or pattern (e.g. 'resume', '*.pdf', 'invoice*2026*') under a folder.
- `folder_size(folder:string)` — Total size and file count of a folder.
- `hash_file(path:string, algorithm?:sha256|md5|sha1|sha512)` — Checksum of a file (to verify a download).
- `image_info(path:string)` — Width, height and type of an image file (PNG, JPEG, GIF, BMP, WebP).
- `largest_files(folder?:string, count?:integer)` — The biggest files under a folder.
- `list_folder(folder?:string, pattern?:string, limit?:integer, sort?:name|newest|largest)` — List what's in a folder ('downloads', 'desktop', 'documents' or a full path).
- `list_zip(zip_path:string)` — What's inside a .zip file.
- ⚠ `move_file(source:string, destination:string)` — Move a file or folder. Asks first.
- `my_folders()` — Where your main folders are (Desktop, Documents, Downloads, Pictures…).
- `old_files(folder?:string, older_than_days?:integer, count?:integer)` — Files not changed for a long time (cleanup candidates).
- `open_file(path:string)` — Open a file with its usual app (documents, photos, music…; programs and scripts are never run).
- ⚠ `organize_by_type(folder?:string)` — Tidy a folder: move its loose files into sub-folders by type (Images, Documents, Videos, Music, Archives, Installers, Other). Asks first.
- `preview_csv_file(path:string, rows?:integer)` — First rows of a CSV file, plus the row count.
- `read_document(path:string, max_chars?:integer)` — Read the text of a Word (.docx), Excel (.xlsx) or PowerPoint (.pptx) file, or any text file.
- `read_file_end(path:string, lines?:integer)` — The last lines of a file (handy for logs).
- `read_text_file(path:string, start_line?:integer, max_lines?:integer)` — Read a text file (or part of it).
- `recent_files(folder?:string, count?:integer, days?:integer)` — Most recently changed files under a folder.
- ⚠ `rename_file(path:string, new_name:string)` — Rename a file or folder (same place, new name). Asks first.
- `search_in_files(text:string, folder?:string, file_pattern?:string, limit?:integer)` — Search for text inside files under a folder (text files only).
- `show_in_explorer(path:string)` — Open File Explorer at a file (selected) or folder.
- ⚠ `unzip_file(zip_path:string, destination?:string)` — Extract a .zip (into a folder next to it by default). Asks first; blocks unsafe paths inside the zip.
- ⚠ `write_text_file(path:string, content:string, overwrite?:boolean)` — Create (or overwrite) a text file in your folders. Asks first.
- ⚠ `zip_files(paths:array, zip_path:string)` — Put files/folders into a .zip. Asks first.

## This PC: hardware, processes, network, settings (42)

- `active_window()` — Which window is in front right now.
- `battery_status()` — Battery level, charging state and time left.
- `clipboard_read()` — What's on the clipboard (text).
- `clipboard_write(text:string)` — Put text on the clipboard (ready to paste).
- `cpu_info()` — Processor model and cores.
- `cpu_usage()` — How busy the processor is right now (measured over half a second).
- `dark_mode(on:boolean)` — Switch Windows dark mode on or off.
- `default_browser()` — Which web browser opens links by default.
- ⚠ `empty_recycle_bin()` — Empty the Recycle Bin for good. Asks first.
- ⚠ `end_process(name_or_pid:string)` — Force-close a running program (unsaved work is lost). Never system processes. Asks first.
- `environment_variable(name:string)` — Value of an environment variable (secret-looking ones are hidden).
- `find_process(name:string)` — Find running programs by name.
- `installed_apps(search?:string)` — Installed programs (optionally filtered by name), with versions.
- `internet_check()` — Is the internet working, and how fast is the first response?
- `listening_ports()` — Network ports this PC is listening on, and which program owns each.
- `lock_pc()` — Lock the PC (sign-in needed to come back).
- `media_control(action:toggle|next|previous)` — Play/pause, next or previous track in whatever is playing.
- `memory_usage()` — RAM in use and free.
- `network_info()` — This PC's local IP, Wi-Fi network and default gateway.
- `open_settings_page(page:string)` — Open a Windows Settings page by its ms-settings name (e.g. bluetooth, display, sound, network-wifi, windowsupdate, apps-volume).
- `open_windows()` — Titles of the app windows open right now.
- `pc_identity()` — PC name, signed-in user and domain/workgroup.
- 🌐 `ping(host:string, count?:integer)` — Ping a public website or server and report the delay.
- `port_free(port:integer)` — Is a local port free for a dev server?
- `power_plan()` — The active power plan.
- `python_versions()` — Python versions installed (from the py launcher).
- `recycle_bin_size()` — How much is in the Recycle Bin.
- `region_settings()` — Time zone, language and region formats.
- `screen_brightness(percent?:integer)` — Read the screen brightness, or set it (0–100) on laptop screens.
- `screen_info()` — Screen resolution, number of monitors and scaling.
- `set_volume(level:up|down|mute|set, percent?:integer)` — Change the speaker volume: up, down, mute/unmute, or set to a percent.
- ⚠ `sleep_pc()` — Put the PC to sleep. Asks first.
- `startup_apps()` — Programs that start when you sign in.
- `system_summary()` — One-glance summary: Windows, CPU, RAM, disk, battery, uptime.
- `take_screenshot()` — Open the screen-snip tool to capture part of the screen.
- `temp_files_size()` — How much space your temporary files use (clean them in Settings → Storage).
- `top_processes(count?:integer)` — Programs using the most memory right now.
- `turn_off_screen()` — Turn off the screen (move the mouse or press a key to wake it).
- `uptime()` — How long since the PC was started.
- `wifi_networks_nearby()` — Wi-Fi networks in range, with signal strength.
- `wifi_status()` — Wi-Fi network name, signal strength and speed.
- `windows_version()` — Windows edition, version and build.

## Control the PC: keys, typing, mouse, windows, apps (24)

- `clipboard_history()` — Open Windows clipboard history (Win+V).
- ⚠ `close_window(name:string)` — Close an app's window politely (it can still ask to save). Asks first.
- `compose_email(to?:string, subject?:string, body?:string)` — Open a new email in your mail app, filled in (you press Send yourself).
- `compose_gmail(to?:string, subject?:string, body?:string)` — Open a Gmail compose window in the browser, filled in (you press Send).
- `emoji_panel()` — Open the Windows emoji panel.
- `find_echo_commands(query:string, limit?:integer)` — Search Echo's 2,700 built-in commands (shortcuts, windows, apps, settings, Office/VS Code/browser keys…) by words.
- `get_selected_text()` — The text selected in the app you were using (your clipboard is put back).
- `google_calendar_event(title:string, start:string, duration_minutes?:integer, details?:string, location?:string)` — Open Google Calendar with a new event filled in (you press Save). start like '2026-11-05 15:30'.
- `mouse_click(button?:left|right|middle|double|triple, x_percent?:number, y_percent?:number)` — Click the mouse (optionally first moving to a spot given as percent across/down the screen).
- `move_mouse(x_percent:number, y_percent:number)` — Move the pointer to a spot (percent across and down the screen).
- `open_app(name:string)` — Start an app from the Start menu by name (Chrome, Word, Spotify, Calculator…).
- `open_directions(destination:string, origin?:string, mode?:driving|walking|bicycling|transit|two-wheeler)` — Open Google Maps directions to a place.
- `open_search(query:string, site?:google|youtube|images|maps|news|amazon|flipkart|wikipedia)` — Open search results for something on Google, YouTube, Maps, Amazon, Wikipedia, GitHub…
- `open_website(url:string)` — Open a web page in the browser.
- `press_keys(keys:string, times?:integer)` — Press a key or shortcut in the app you were using: 'ctrl+s', 'alt+tab', 'enter', 'ctrl+k ctrl+w' (a sequence).
- 📱 `run_echo_command(phrase:string)` — Run one of Echo's built-in commands by its phrase (e.g. 'snap this window left', 'open bluetooth settings', 'new tab').
- `scroll(direction:up|down|left|right, amount?:integer)` — Scroll in the window under the pointer.
- `show_desktop()` — Show the desktop (press again to bring windows back).
- `switch_to_window(name:string)` — Bring an open app or window to the front by app name or title words.
- `transform_selection(operation:string)` — Change the text selected in your app, in place: UPPER, LOWER, TITLE, SORT_LINES, JSON_PRETTY, B64_ENC, SNAKE, BULLETS, … (undo with Ctrl+Z).
- `type_text(text:string)` — Type text into the app you were using (long text is pasted, then your clipboard is put back).
- `virtual_desktop(action:new|next|previous|close|task_view)` — Make, switch or close virtual desktops, or open Task View.
- `whatsapp_message(text:string, phone?:string)` — Open WhatsApp with a message ready (to a number with country code, or pick the chat yourself). You press Send.
- `window_action(action:maximize|minimize|restore|close|snap_left|snap_right|snap_top_left|snap_top_right)` — Do something with the window you were using: maximize, snap left/right/corners, close, keep on top…

## Live information from the internet (88)

- 🌐 `address_from_coordinates(lat:number, lon:number)` — Place name for coordinates (OpenStreetMap).
- 🌐 `air_quality(city?:string)` — Air quality (US AQI, PM2.5, PM10).
- 🌐 `air_quality_forecast(city?:string, days?:integer)` — Daily peak US AQI forecast for the next days.
- 🌐 `animal_picture(animal?:dog|cat)` — Link to a random dog or cat picture.
- 🌐 `arxiv_search(query:string, count?:integer)` — Research papers on arXiv.
- 🌐 `book_info(title:string)` — Who wrote a book and when it was first published.
- 🌐 `books_by_author(author:string)` — Well-known books by an author.
- 🌐 `cat_fact()` — A fact about cats.
- 🌐 `crates_search(query:string, count?:integer)` — Search crates.io for Rust libraries.
- 🌐 `currency_history(base:string, target:string, days?:integer)` — How an exchange rate moved over recent days.
- 🌐 `currency_info(code:string)` — Today's value of a currency against major ones.
- 🌐 `define_word(word:string)` — Dictionary definition of an English word.
- 🌐 `dev_articles(tag?:string, count?:integer)` — Popular DEV Community articles (optionally by tag).
- 🌐 `distance_between(place_a:string, place_b:string)` — Straight-line distance between two places (roads are usually 20–40% longer).
- 🌐 `dns_lookup(host:string)` — IP addresses a domain name resolves to.
- 🌐 `docker_image_tags(name:string)` — Latest tags of an official Docker image.
- 🌐 `doi_lookup(doi:string)` — Title, authors, journal and year for a DOI.
- 🌐 `domain_info(domain:string)` — Whether a domain is registered, since when, and when it expires.
- 🌐 `earthquakes_today()` — Significant earthquakes in the last day.
- 🌐 `elevation(place:string)` — Height above sea level of a place.
- 🌐 `expand_link(url:string)` — Where a (short) link really goes.
- 🌐 `f1_next_race()` — The next Formula 1 race and when it starts.
- 🌐 `f1_standings()` — Current Formula 1 drivers' championship.
- 🌐 `fetch(url:string, max_length?:integer, start_index?:integer, raw?:boolean)` — Fetch a URL and return its readable text (or raw HTML/JSON with raw=true). Long pages: use start_index to read on.
- 🌐 `find_pdf(topic:string)` — Find PDF documents about a topic.
- 🌐 `find_place(place:string)` — Latitude, longitude, country and time zone of a place.
- 🌐 `food_product(barcode:string)` — Product name, brand, ingredients and nutrition grade from a food barcode (Open Food Facts).
- 🌐 `github_file(repo:string, path:string, branch?:string)` — Read a file from a public GitHub repository.
- 🌐 `github_issues(repo:string, state?:open|closed|all, count?:integer)` — Recent issues of a GitHub repository.
- 🌐 `github_latest_release(repo:string)` — Latest release of a GitHub repository.
- 🌐 `github_readme(repo:string, max_chars?:integer)` — A GitHub repository's README text.
- 🌐 `github_repo(repo:string)` — GitHub repository stats (stars, forks, issues, language, last push). 'owner/name' or a search term.
- 🌐 `github_search(query:string, count?:integer, language?:string)` — Search GitHub repositories (most stars first).
- 🌐 `github_user(user:string)` — A GitHub user's profile.
- 🌐 `hacker_news(feed?:top|new|best|ask|show)` — Hacker News stories.
- 🌐 `hacker_news_search(query:string)` — Search Hacker News stories.
- 🌐 `http_headers(url:string)` — Notable HTTP response headers of a site.
- 🌐 `inspiring_quote()` — An inspiring quote.
- 🌐 `ip_lookup(ip:string)` — Where an IP address is and who runs it.
- 🌐 `joke()` — A fresh joke (ask for the punchline with the answer).
- 🌐 `lobsters_hot(count?:integer)` — Hottest stories on Lobsters (a programming link community).
- 🌐 `mocktail_idea()` — A non-alcoholic drink recipe.
- 🌐 `music_search(query:string, kind?:song|album|podcast|audiobook, count?:integer)` — Find songs, albums, podcasts or audiobooks (Apple's catalogue).
- 🌐 `my_public_ip()` — This connection's public IP address.
- 🌐 `nasa_picture_of_the_day()` — NASA's astronomy picture of the day.
- 🌐 `news_headlines(topic?:top|world|india|business|technology|sports|science|health)` — Latest headlines (top stories or a topic).
- 🌐 `news_search(query:string)` — Latest headlines about something.
- 🌐 `npm_package_details(name:string)` — npm package details: version, license, dependencies, homepage, weekly downloads.
- 🌐 `npm_search(query:string, count?:integer)` — Search npm for packages.
- 🌐 `official_website(name:string)` — The official website of an organisation, product or place.
- 🌐 `on_this_day()` — What happened on this day in history.
- 🌐 `package_version(name:string, registry:npm|pypi|crates|nuget|rubygems|pub|homebrew|maven)` — Latest version (and summary) of a package on npm, PyPI, crates.io, NuGet, RubyGems, pub.dev, Homebrew or Maven.
- 🌐 `page_headings(url:string)` — The headings (outline) of a web page.
- 🌐 `page_links(url:string, filter_text?:string)` — Links on a web page (optionally only those whose text or URL contains some words).
- 🌐 `page_metadata(url:string)` — A web page's title, description, preview image and language.
- 🌐 `people_in_space()` — Who is in space right now.
- 🌐 `public_holidays(country:string)` — Upcoming public holidays in a country (most countries; not India's lunar festivals).
- 🌐 `pypi_package_details(name:string)` — PyPI package details: version, Python needed, license, dependencies, links.
- 🌐 `qr_code_link(text:string, size?:integer)` — A link to a QR code image for some text or a URL (open it to view, save or print).
- 🌐 `random_advice()` — A random piece of advice.
- 🌐 `random_fact()` — A random (useless but true-ish) fact.
- 🌐 `read_rss_feed(url:string, count?:integer)` — Latest items from any RSS/Atom feed.
- 🌐 `recipe(dish?:string)` — A recipe with ingredients (random if no dish given).
- 🌐 `related_words(word:string, relation?:synonyms|antonyms|rhymes|sounds_like|means_like|describing|starts_with)` — Synonyms, opposites, rhymes, sound-alikes, words for a meaning, describing words, or words starting with letters.
- 🌐 `robots_txt(site:string)` — A site's robots.txt rules.
- 🌐 `service_status(service:string)` — Official status of a service (GitHub, OpenAI, Anthropic, Discord, Cloudflare, npm, PyPI, Zoom, Notion… 57 services).
- 🌐 `shorten_link(url:string)` — Make a short link (is.gd).
- 🌐 `slang_meaning(term:string)` — What a slang term means (Urban Dictionary; may be crude).
- 🌐 `space_station_location()` — Where the International Space Station is right now.
- 🌐 `ssl_certificate(site:string)` — When a site's HTTPS certificate expires and who issued it.
- 🌐 `stackoverflow_search(query:string, count?:integer)` — Top Stack Overflow questions for a problem.
- 🌐 `sun_times(city?:string)` — Sunrise and sunset today.
- 🌐 `translate(text:string, language:string)` — Translate English text into another language (Hindi, Telugu, Tamil, Spanish…).
- 🌐 `trivia_question()` — A multiple-choice trivia question (answer included at the end).
- 🌐 `tv_schedule(country?:string)` — Today's TV schedule highlights in a country (two-letter code).
- 🌐 `tv_show(name:string)` — About a TV series: network, years, rating, summary.
- 🌐 `wayback_snapshot(url:string)` — The closest saved copy of a page on the Internet Archive's Wayback Machine.
- 🌐 `weather_advice(question:umbrella|jacket|walk|rain|snow|tonight|hot_or_cold, city?:string)` — Practical weather answers: do I need an umbrella or jacket, good for a walk, rain or snow coming, tonight's low.
- 🌐 `weather_detail(what:humidity|wind|uv|feels_like, city?:string)` — Humidity, wind, UV index or feels-like temperature.
- 🌐 `weather_forecast(city?:string, day?:today|tomorrow|week|weekend)` — Forecast for today, tomorrow, the week or the weekend.
- 🌐 `weather_hourly(city?:string)` — Weather for the next few hours.
- 🌐 `weather_now(city?:string)` — Current weather in a city (or where you are).
- 🌐 `web_search_results(query:string)` — Top web results (titles and snippets) for a search.
- 🌐 `website_status(site:string)` — Is a website up? Status code and response time.
- 🌐 `wikipedia_featured()` — Today's featured Wikipedia article.
- 🌐 `wikipedia_random()` — A random Wikipedia article summary.
- 🌐 `wikipedia_search(query:string, limit?:integer)` — Wikipedia article titles matching a search.
- 🌐 `wikipedia_summary(topic:string)` — Short Wikipedia summary of a person, place or thing.

## Health, home, cooking, travel calculators (18)

- `ac_size_for_room(room_length_m:number, room_width_m:number, sunny?:boolean, people?:integer)` — Rough AC size (tons) for a room.
- `bmi(weight_kg:number, height_cm:number)` — Body mass index with the standard and Asian-Indian categories.
- `calories_burned(activity:string, minutes:number, weight_kg:number)` — Calories burned by an activity (MET estimate).
- `daily_calories(weight_kg:number, height_cm:number, age:integer, sex:male|female, activity?:sitting|light|moderate|active|very_active)` — Calories a day to keep weight steady (Mifflin-St Jeor), plus lose/gain targets.
- `dose_schedule(medicine_times:array, days?:integer)` — A printable dose schedule for times each day (to tick off).
- `healthy_weight_range(height_cm:number, sex?:male|female)` — Healthy weight range for a height (BMI 18.5–24.9) and the Devine formula.
- `heart_rate_zones(age:integer, resting_hr?:integer)` — Training heart-rate zones (max ≈ 220 − age; Karvonen if resting rate given).
- `life_in_numbers(birth_date:string)` — Fun numbers about your life so far (days, weeks, approximate heartbeats and breaths).
- `pace(distance_km:number, minutes:number)` — Pace (minutes per km) and speed for a run or walk.
- `paint_needed(area_sqft:number, coats?:integer, coverage_sqft_per_litre?:number)` — Litres of paint for a wall area.
- `party_food_quantity(people:integer, dish?:biryani|rice|chapati|curry|dal|sweets|snacks|drinks)` — How much food to make for a number of guests (rough averages).
- `pregnancy_due_date(last_period:string, cycle_days?:integer)` — Estimated due date (Naegele's rule) and current week of pregnancy.
- `scale_recipe(servings_from:number, servings_to:number, ingredients:array)` — Scale recipe quantities to a different number of servings.
- `tidy_shopping_list(items:array)` — Group a shopping list by aisle and merge repeats.
- `tiles_needed(room_length_ft:number, room_width_ft:number, tile_size_in?:number, wastage_percent?:number)` — Number of square floor tiles for a room (with wastage).
- `travel_time(distance_km:number, speed_kmh:number, breaks_minutes?:integer)` — How long a journey takes at an average speed.
- `usage_trend(bill_units:array)` — Average and trend of monthly readings (electricity units, data GB, spending…).
- `water_intake(weight_kg:number, active_minutes?:integer, hot_weather?:boolean)` — Rough daily water need.

## India: PAN, GSTIN, IFSC, PIN codes, lakh/crore (10)

- `aadhaar_format_check(number:string)` — Check whether a 12-digit Aadhaar number is well-formed (catches typos). Offline; the number isn't stored or sent.
- `gstin_check(gstin:string)` — Check a GSTIN's format and checksum, and name its state.
- `ifsc_format_check(ifsc:string)` — Check an IFSC code's format and name the bank code.
- 🌐 `ifsc_lookup(ifsc:string)` — Bank, branch and address for an IFSC code (live).
- `indian_mobile_check(number:string)` — Check an Indian mobile number's format and tidy it.
- `pan_check(pan:string)` — Check a PAN's format and say what kind of holder it is for.
- 🌐 `pincode_lookup(pincode:string)` — Post offices, district and state for an Indian PIN code (live).
- `rupees_in_words(amount:number)` — Amount in Indian words, as on a cheque ('One crore twenty-five lakh … rupees and seventy-five paise only').
- `upi_id_check(upi_id:string)` — Check a UPI ID's format (name@bank). Reminder: you never need your PIN to receive money.
- `vehicle_number_check(plate:string)` — Check a vehicle registration number's format and name its state.

## Developer tools: git, code stats, templates, HTTP (31)

- `basic_auth_header(username:string, password:string)` — The HTTP Basic Authorization header for a username and password (for testing your own APIs).
- `branch_name(text:string, kind?:feature|fix|chore|docs)` — A tidy git branch name from a description.
- `ci_workflow_template(kind:python|node)` — A starter GitHub Actions workflow that runs tests on every push.
- `code_stats(folder:string)` — Lines of code per language in a project folder.
- `commit_message_check(message:string)` — Check a commit message against Conventional Commits (feat:, fix:, docs:…).
- `curl_to_python(command:string)` — Convert a curl command into Python requests code.
- `dockerfile_template(kind:python|node|static|go)` — A starter Dockerfile.
- `env_example(text:string)` — A shareable .env.example from a .env (same names, values removed).
- `estimate_tokens(text:string)` — Rough count of AI tokens in a text (≈ 4 characters or ¾ of a word each).
- `find_todos(folder:string)` — TODO / FIXME / HACK / XXX comments in a project.
- `git_branches(repo:string)` — Local branches (current marked with *) and their last commit.
- `git_contributors(repo:string)` — Who committed, and how many commits each.
- `git_diff_summary(repo:string, staged?:boolean)` — Which files changed and how much (diff --stat).
- `git_last_commit(repo:string)` — The latest commit with the files it changed.
- `git_log(repo:string, count?:integer)` — Recent commits of a repository.
- `git_remotes(repo:string)` — The repository's remotes.
- `git_status(repo:string)` — git status of a repository (path or workspace name): branch, changed and untracked files.
- `gitignore_template(kind:python|node|java|android|dotnet|go|rust|unity)` — A starter .gitignore.
- `html_tag_check(text:string)` — Check that HTML tags are balanced (finds unclosed or stray closing tags).
- 🌐 `http_request(url:string, method?:GET|HEAD|POST|PUT|PATCH|DELETE, body?:string, headers?:object)` — Call a public web API (GET/HEAD freely; POST/PUT/PATCH/DELETE ask you first). Private/local addresses are refused.
- `json_to_dataclass(text:string, name?:string)` — Python dataclasses from an example JSON object.
- `json_to_typescript(text:string, name?:string)` — TypeScript interfaces from an example JSON object.
- `license_text(license:MIT|ISC|BSD-2-Clause, holder:string, year?:integer)` — Full text of a short open-source licence.
- `list_workspaces()` — Your project folders set in Echo's Settings (Workspaces).
- `minify_css(css:string)` — Minify CSS.
- `open_localhost(port:integer, path?:string)` — Open your local dev server (http://localhost:PORT) in the browser.
- `parse_user_agent(user_agent:string)` — Which browser and operating system a User-Agent string describes.
- `project_dependencies(folder:string)` — Dependencies declared by a project (package.json, requirements.txt, pyproject.toml, Cargo.toml, go.mod).
- `python_imports(code:string)` — Modules a piece of Python code imports.
- `python_syntax_check(code:string)` — Check Python code for syntax errors (it isn't run).
- `readme_template(name:string, description:string, language?:python|node|other)` — A starter README.md.

## Your lists, notes, memories, timers, messages (15)

- ⚠ `calendar_file(title:string, start:string, duration_minutes?:integer, location?:string, notes?:string, remind_minutes?:integer)` — Make a calendar event file (.ics) in Downloads and open it, so Outlook/Calendar can add it. start like '2026-11-05 15:30'. Asks first.
- ⚠ 📱 `forget(phrase:string)` — Forget memories matching a phrase. Asks first.
- 📱 `list_add(items:array, list_name?:string)` — Add items to one of your lists (shopping, to-do, packing…).
- ⚠ 📱 `list_clear(list_name:string)` — Empty a list. Asks first.
- 📱 `list_remove(item:string, list_name?:string)` — Remove (tick off) an item from a list.
- 📱 `list_show(list_name?:string)` — What's on a list.
- 📱 `list_timers()` — Timers that are running.
- 📱 `lists_all()` — All your lists with item counts.
- 📱 `note_add(text:string)` — Save a short note (passwords and codes are refused).
- 📱 `notes_search(query?:string)` — Your notes, newest first (optionally only those containing some words).
- 📱 `recall(query?:string)` — What Echo remembers about the user (optionally matching some words).
- 📱 `remember(fact:string)` — Remember a lasting fact or preference about the user (never passwords, codes or card numbers).
- 📱 `remind_at(time_text:string, message:string)` — Remind the user at a clock time today (or tomorrow if that time has passed).
- 📱 `set_timer(minutes:number, label?:string)` — Start a timer (Echo announces it when it ends).
- 📱 `show_message(text:string)` — Show a message in Echo's window (for results the user should see).

## Moltbook, the social network for AI agents: read, search, and (with your OK) post (14)

- 🌐 `moltbook_agent(name:string)` — An agent's Moltbook profile: description, karma, followers and its human owner's public X handle.
- ⚠ 🌐 📱 `moltbook_comment(post_id:string, content:string, reply_to_comment?:string)` — Comment on a Moltbook post (or reply to a comment) as Echo — you approve the text.
- 🌐 `moltbook_communities(limit?:integer)` — Moltbook's communities ('submolts') with member counts.
- 🌐 `moltbook_feed(sort?:hot|new|top|rising, community?:string, limit?:integer)` — What AI agents are posting on Moltbook right now (whole site, or one community like 'general' or 'agents').
- ⚠ 🌐 📱 `moltbook_follow(agent_name:string, follow?:boolean)` — Follow or unfollow an agent on Moltbook as Echo. Asks first.
- ⚠ 📱 `moltbook_join(agent_name:string, description:string)` — Create a Moltbook account for Echo. You then verify it (email + a post on X) using the claim link. Asks first.
- 🌐 📱 `moltbook_my_account()` — Echo's Moltbook account: claim status, karma, unread notifications and activity on its posts.
- 🌐 📱 `moltbook_my_feed(only_following?:boolean, limit?:integer)` — Echo's personalised Moltbook feed (communities it subscribes to and agents it follows).
- ⚠ 🌐 📱 `moltbook_post(community:string, title:string, content?:string, link?:string)` — Publish a post on Moltbook as Echo (you see the exact text and approve it).
- 🌐 `moltbook_read_post(post_id:string, comments?:integer)` — Read one Moltbook post and its top comments.
- 🌐 `moltbook_search(query:string, kind?:all|posts|comments, limit?:integer)` — Search Moltbook by meaning (e.g. 'how do agents handle memory') — finds agent posts and comments on a topic.
- ⚠ 🌐 📱 `moltbook_subscribe(community:string, subscribe?:boolean)` — Subscribe Echo to a Moltbook community (or unsubscribe). Asks first.
- 🌐 📱 `moltbook_verify(verification_code:string, answer:number)` — Answer Moltbook's anti-spam maths challenge for Echo's own new post or comment.
- ⚠ 🌐 📱 `moltbook_vote(post_id:string, direction?:up|down)` — Upvote or downvote a Moltbook post as Echo. Asks first.

## Watches, reports, comparisons, trends and dashboards on any data; the 1,000 automation ideas; briefings (31)

- `automation_archive(keep_days?:integer, source?:string)` — Zip up saved readings older than N days (all sources or one).
- `automation_bundle(sources:array)` — Collect several sources into one diagnostic zip (Downloads\Echo reports) to share with support.
- `automation_check(source:string, rule:string, params?:object)` — Items in a source matching a rule like 'free_percent < 10', 'status != OK and start == Automatic', 'count > 0'.
- `automation_compare(source:string, params?:object, against?:last|first)` — Compare a source now with its last (or first) saved reading: what was added, removed or changed.
- `automation_dashboard(sources:array)` — Make and open an HTML dashboard (a file, no server) for several sources, with trend lines from history.
- `automation_events_around(minutes_ago?:number, window_minutes?:integer)` — Windows warnings and errors around a moment (minutes ago), to explain a change.
- `automation_export_csv(source:string, params?:object)` — Export a source to a timestamped CSV in Downloads\Echo reports.
- `automation_history_search(text:string, source?:string, params?:object)` — Search every saved reading (or one source's) for some text — 'when was this app installed / this device seen'.
- `automation_report(source:string, params?:object, save_snapshot?:boolean)` — Read a source now and summarise it (and keep the reading in history). params for generic sources: path / url / tool.
- `automation_sources()` — Data sources Echo can read, watch and compare (built-in PC probes, plus files, folders, pages, APIs, feeds, tools).
- `automation_stale_data(source:string, max_age_days?:number, params?:object)` — Missing values and dates older than N days in a source.
- `automation_trend(source:string, field:string, item?:string, threshold?:number, params?:object)` — Trend of a number over saved readings, and when it would reach a threshold.
- `automation_unusual_changes(source:string, params?:object, jump_percent?:number)` — Unusual changes since the last reading (big jumps, new or missing items) with the likely cause.
- `automation_validate(source:string, rules:array, params?:object)` — Check a source against a policy (each rule describes a problem; ✓ means no item has it).
- 🌐 `daily_briefing(city?:string, topics?:array)` — One morning briefing: date, weather, headlines, timers, lists and anything on the PC that needs attention.
- `idea_coverage()` — How the 1,000 ideas are covered: built-in data, related data, your own data, or not on Windows.
- `idea_find(query:string, limit?:integer)` — Find ideas in the 1,000-idea automation list by words.
- `idea_run(number:integer, params?:object)` — Do idea #N from the 1,000-idea list (101–1100). params: path/url/tool for your own data; rule(s), field, threshold, every_minutes, at (HH:MM), profile, keep_days as the idea needs.
- `idea_show(number:integer)` — Details of idea #N: area, action, subject and which data it uses.
- `pc_checkup()` — Full PC check-up: storage, disk health, Windows errors, device problems, crashes, pending restart, Defender, firewall, battery, memory.
- 🌐 `price_alert(url:string, below:number, every_minutes?:integer)` — Tell me when the first price shown on a product page drops below an amount.
- `recovery_checklist(area:string, problem:string)` — Step-by-step recovery checklist for a kind of failure.
- `schedule_tool(tool_name:string, args?:object, daily_at?:string, every_minutes?:integer)` — Run any read-only Echo tool on a schedule and send me the result (e.g. weather_forecast daily at 07:30).
- ⚠ `settings_profile_apply(profile:object)` — Apply a settings profile (e.g. {'dark_mode': true, 'power_plan': 'Power saver'}). Shows the changes and asks first.
- `settings_profile_preview(profile:object)` — Dry run: what a settings profile would change (dark_mode, pointer_size, sticky_keys, double_click_ms, power_plan, brightness).
- `watch_create(name:string, source:string, kind?:check|changes|report|trend, rules?:array, every_minutes?:integer, daily_at?:string, params?:object, field?:string, threshold?:number)` — Watch a source on a schedule (every N minutes or daily at HH:MM). check = tell me when a rule matches; changes = tell me what changed; report = send a summary; trend = keep readings for trends. Runs inside the Echo app.
- `watch_list()` — All watches with their schedule and last result.
- `watch_remove(watch_id:string)` — Stop and delete a watch.
- `watch_run_now(watch_id:string)` — Run a watch right now and show its result.
- 🌐 `watch_web_page(url:string, contains?:string, every_minutes?:integer)` — Tell me when a web page changes (optionally only the lines containing some words).
- `what_changed()` — What changed on this PC since the last check: installed apps, startup apps, updates, drivers… (first run saves a baseline).

## Your personal assistant: tasks and due dates, plan my day, follow-ups, people and birthdays, habits, expenses and budgets, journal, focus sessions, meeting notes, my day, weekly review, taught phrases (33)

- `birthday_add(text:string)` — Save a birthday: "Ravi 3 May", "Mom's birthday is 12/08".
- `birthdays_upcoming(days?:integer)` — Birthdays in the next N days.
- `budget_set(monthly_amount:number, category?:string)` — Set a monthly budget, overall ("total") or for a category (food, transport, shopping…).
- `contacted(name:string, how?:string)` — Log that you talked to someone (call, met, message).
- `expense_add(text:string, amount?:number, category?:string)` — Log money you spent: "250 on lunch", "₹1,200 petrol", "2k amazon shoes". Category is guessed if not given.
- `expenses(period?:string)` — What you spent: today, week, month (default), last month, or YYYY-MM — by category, with your budget.
- `focus_start(minutes?:integer, task?:string)` — Start a focus session (Pomodoro): a timer, and the session is logged for your weekly review.
- `focus_stats(days?:integer)` — Focus minutes in the last N days, by day and by task.
- `follow_up(text:string)` — Remember to follow up with someone or on something ("Ravi about the invoice in 3 days"). Default: in 3 days.
- `follow_up_done(item:string)` — Close a follow-up.
- `follow_ups(view?:due|all)` — Follow-ups that are due now (or all open ones).
- `habit_add(name:string, per_week?:integer)` — Start tracking a habit (how many days a week you aim for).
- `habit_done(name:string, day?:string)` — Tick off a habit for today (or another day).
- `habits()` — Your habits: this week's count against the goal, and current streaks.
- `journal_add(text:string, mood?:integer)` — Write a journal entry. Mood 1–5 (guessed from your words if you don't say).
- `journal_read(days?:integer, query?:string)` — Recent journal entries (or ones mentioning `query`) and your average mood.
- `meeting_save(title:string, notes:string, action_items_list?:array, make_tasks?:boolean)` — Save meeting notes; action items (from the list, or found in the notes: "TODO", "- [ ]", "Ravi will …") become tasks tagged #meeting with any due date they mention.
- `meetings(query?:string)` — Recent meetings, or the ones whose title/notes mention `query`.
- `my_day()` — Your personal brief for today: what's overdue and due, follow-ups, birthdays, habits left, money, and the one thing to start with.
- `people_to_reconnect(days?:integer)` — People you haven't talked to in N days (from what you've logged).
- `person_note(name:string, note:string)` — Remember something about a person (preferences, family, what you talked about). "birthday is 3 May" sets the birthday.
- `person_show(name:string)` — Everything you told Echo about someone: notes, birthday, when you last talked.
- ⚠ `phrase_forget(phrase:string)` — Forget a phrase you taught (asks first).
- `phrases_taught()` — The phrases you've taught Echo.
- `plan_my_day(busy?:string, end?:string, start?:string, break_minutes?:integer)` — Time-block today: fits your open tasks (overdue and important first) into the free time between now (or `start`) and `end`, around busy times you name ("11-12 standup, 3pm-4pm call"), with short breaks.
- `task_add(text:string, due?:string, priority?:low|normal|high|, project?:string, minutes?:integer, repeat?:|daily|weekdays|weekly|monthly)` — Add a task. Say the due date in plain words ("tomorrow 5pm", "by friday", "in 3 days"); "!high" or "urgent" marks it important, "#work" puts it in a project, "~45m" says how long it takes.
- ⚠ `task_delete(task:string)` — Delete a task for good (asks first).
- `task_done(task:string)` — Mark a task done (by its words or id). Repeating tasks move to their next date.
- `task_snooze(task:string, until?:string)` — Move a task to a later date/time.
- `tasks(view?:today|overdue|upcoming|all|done|nodate, project?:string)` — Your tasks: today (overdue + due today + important), overdue, upcoming (next 7 days), all, done, or nodate.
- `teach_phrase(text:string)` — Teach Echo your own phrase: "work mode = open VS Code, open Teams, do not disturb on". Each step is a normal Echo command; saying the phrase runs them in order (only safe kinds of commands).
- `weekly_review()` — The last 7 days: tasks finished, still overdue, habits, focus time, spending, mood — and people to catch up with.
- `what_next(minutes_free?:integer)` — The one task to do now: overdue first, then important, then soonest due — and it fits the time you have.
