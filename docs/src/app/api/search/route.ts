import { source } from '@/libs/source';
import { createFromSource } from 'fumadocs-core/search/server';

// Set to false for static exports or modify as needed
export const revalidate = 3600; // Revalidate every hour

export const { GET } = createFromSource(source); 