/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: process.env.NEXT_PUBLIC_API_URL ?
                    `${process.env.NEXT_PUBLIC_API_URL.replace('/api/v1', '')}/:path*` :
                    'http://localhost:8000/:path*',
            },
        ]
    },
    images: {
        domains: ['localhost'],
    },
}

module.exports = nextConfig 