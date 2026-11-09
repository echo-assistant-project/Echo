---
name: coding-interview-prep
description: Prepare for software engineering interviews — data structures and algorithms, problem-solving method, Big-O, system design basics and behavioural answers. Use for "prepare me for a coding interview", "solve this LeetCode problem", "explain Big-O", "practise DSA", "mock interview".
audience: developers
field: Technology
courses: MIT 6.006 Introduction to Algorithms (MIT OpenCourseWare) | https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/ ; Tech Interview Handbook | https://www.techinterviewhandbook.org/ ; NPTEL Programming, Data Structures and Algorithms | https://nptel.ac.in/ ; CS50x (Harvard) | https://cs50.harvard.edu/x/
source: Echo (written for Echo from these courses' syllabi)
license: same as Echo
---

# Coding interview preparation

## 1. The problem-solving routine (say it out loud)
1. Restate the problem and ask about input size, edge cases, duplicates, negative numbers.
2. Walk through a small example by hand.
3. State a brute-force idea and its cost; then improve.
4. Write clean code, naming things well.
5. Test with the example, an edge case (empty, one item), and a tricky case.
6. State time and space complexity.

## 2. Big-O in one minute
O(1) constant, O(log n) halving (binary search), O(n) one pass, O(n log n) good sorting, O(n²) nested loops, O(2ⁿ) trying all subsets. Interviews usually want the step from O(n²) to O(n) or O(n log n).

## 3. The patterns that cover most questions
Hash map for counting/lookup · two pointers on sorted arrays · sliding window for subarrays/substrings · stack for brackets and "next greater" · binary search on sorted data or on the answer · BFS for shortest path in unweighted graphs, DFS for exploring · heap for top-k · prefix sums · intervals (sort by start) · dynamic programming (define state, recurrence, base case) · backtracking for permutations/combinations.

## 4. A study plan (8 weeks)
Weeks 1–2 arrays, strings, hash maps · 3 linked lists, stacks, queues · 4 trees and BFS/DFS · 5 graphs and heaps · 6 binary search and greedy · 7 dynamic programming · 8 mock interviews. Aim for 2–3 problems a day; re-solve the ones you failed after 3 days.

## 5. System design basics (for experienced roles)
Clarify requirements and scale → API → data model → high-level boxes (load balancer, app servers, database, cache, queue) → bottlenecks and trade-offs (consistency vs availability, read vs write heavy).

## 6. Behavioural questions
Prepare 6 stories with **STAR** (Situation, Task, Action, Result — with numbers): a hard bug, a conflict, a failure, leadership, tight deadline, learning something fast.

## 7. As a mock interviewer
Give one problem at a time, don't reveal the answer, give hints in steps (pattern → data structure → key idea), and end with specific feedback on communication, correctness and complexity.
