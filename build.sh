#!/bin/bash
# Vercel build script for PDF Processor Tool

echo "Building PDF Processor Tool for Vercel..."

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install

# Build frontend
echo "Building frontend..."
npm run build

# Go back to root
cd ..

echo "Build completed successfully!"
