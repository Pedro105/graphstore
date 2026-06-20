"""Relational store (Postgres/Supabase) for auth concerns.

FalkorDB remains the graph + vector store; this package holds only what needs
a relational store: users, API keys, and the usage log. See db/postgres.py.
"""
