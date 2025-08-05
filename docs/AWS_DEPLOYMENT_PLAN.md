# AWS Deployment Plan: Bowls Club Application

## Executive Summary

This document outlines the comprehensive changes required to migrate the Bowls Club Flask application from a local development environment to AWS Elastic Beanstalk with PostgreSQL database and S3 file storage.

### Current Architecture
- **Application**: Flask web application with SQLAlchemy ORM
- **Database**: SQLite with Flask-Migrate for schema management
- **File Storage**: Local filesystem with secure storage paths
- **Session Management**: Flask-Session with file-based storage

### Target Architecture
- **Application**: Flask on AWS Elastic Beanstalk
- **Database**: Amazon RDS PostgreSQL
- **File Storage**: Amazon S3 with CloudFront CDN
- **Session Management**: Database-backed sessions or Redis
- **Logging**: CloudWatch integration

---

## 1. Database Migration: SQLite → PostgreSQL

### 1.1 Current Database Analysis

**Current Setup:**
- SQLite database: `sqlite:///app.db`
- 12 core models with complex relationships
- Flask-Migrate for schema management
- Comprehensive audit logging system

**Models Overview:**
- **Core**: Member, Role, Event, Booking, Post, PolicyPage
- **Team Management**: EventTeam, TeamMember, BookingTeam, BookingTeamMember, BookingPlayer
- **Association Tables**: member_roles, event_member_managers

### 1.2 PostgreSQL Migration Tasks

#### A. Database Configuration Updates

**File: `config.py`**
```python
# Current
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.db')

# New
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
    'postgresql://user:password@localhost/bowls_club'

# Additional PostgreSQL-specific configurations
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0
}
```

#### B. Dependencies Update

**File: `requirements.txt`**
```txt
# Add PostgreSQL driver
psycopg2-binary>=2.9.0

# Update SQLAlchemy if needed
SQLAlchemy>=2.0.0
```

#### C. Migration Script Updates

**New Migration Environment Setup:**
```bash
# Create new migration environment for PostgreSQL
flask db init --directory migrations_postgres
flask db migrate -m "Initial PostgreSQL schema" --directory migrations_postgres
```

**Migration Script Changes:**
- Remove `batch_alter_table` usage (PostgreSQL doesn't need it)
- Update NOT NULL column handling
- Review cascade deletion behavior

#### D. Model Adjustments

**File: `app/models.py`**
```python
# Review and update any SQLite-specific patterns
class Member(db.Model):
    # Ensure boolean fields have proper defaults
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    lockout = db.Column(db.Boolean, default=False, nullable=False)
    
    # Review auto-increment behavior
    id = db.Column(db.Integer, primary_key=True)
```

### 1.3 Data Migration Strategy

1. **Export current SQLite data**
2. **Create PostgreSQL database on RDS**
3. **Run schema migrations**
4. **Import data with proper type conversions**
5. **Verify data integrity and relationships**

---

## 2. File Storage Migration: Local Filesystem → S3

### 2.1 Current File Storage Analysis

**Current Structure:**
- **Posts**: `secure_storage/posts/` (Markdown + HTML files)
- **Archives**: `secure_storage/archive/` (Deleted posts)
- **Policy Pages**: `secure_storage/policy_pages/` (Markdown + HTML files)
- **Static Files**: `app/static/` (CSS, images, assets)

**Security Features:**
- UUID-based filenames
- Path validation against traversal attacks
- Files stored outside web root
- HTML sanitization

### 2.2 S3 Migration Implementation

#### A. S3 Configuration

**File: `config.py`**
```python
# S3 Configuration
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_BUCKET_NAME = os.environ.get('AWS_S3_BUCKET_NAME')
AWS_S3_CUSTOM_DOMAIN = os.environ.get('AWS_S3_CUSTOM_DOMAIN')  # CloudFront domain

# S3 Bucket structure
S3_POSTS_PREFIX = 'posts/'
S3_ARCHIVE_PREFIX = 'archive/'
S3_POLICY_PAGES_PREFIX = 'policy-pages/'
S3_STATIC_PREFIX = 'static/'
```

#### B. S3 Service Layer

**New File: `app/services/s3_service.py`**
```python
import boto3
from botocore.exceptions import ClientError
from flask import current_app
import os
import logging

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config['AWS_S3_REGION_NAME']
        )
        self.bucket_name = current_app.config['AWS_S3_BUCKET_NAME']
    
    def upload_file(self, file_obj, key, content_type=None):
        """Upload file to S3 with proper security headers"""
        try:
            extra_args = {
                'ServerSideEncryption': 'AES256',
                'ACL': 'private'
            }
            if content_type:
                extra_args['ContentType'] = content_type
            
            self.s3_client.upload_fileobj(
                file_obj, 
                self.bucket_name, 
                key, 
                ExtraArgs=extra_args
            )
            return True
        except ClientError as e:
            logging.error(f"S3 upload failed: {e}")
            return False
    
    def download_file(self, key):
        """Download file from S3"""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return response['Body'].read()
        except ClientError as e:
            logging.error(f"S3 download failed: {e}")
            return None
    
    def delete_file(self, key):
        """Delete file from S3"""
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=key
            )
            return True
        except ClientError as e:
            logging.error(f"S3 delete failed: {e}")
            return False
    
    def move_file(self, source_key, dest_key):
        """Move file within S3 (copy and delete)"""
        try:
            # Copy to new location
            self.s3_client.copy_object(
                Bucket=self.bucket_name,
                CopySource={'Bucket': self.bucket_name, 'Key': source_key},
                Key=dest_key,
                ServerSideEncryption='AES256',
                ACL='private'
            )
            # Delete original
            self.delete_file(source_key)
            return True
        except ClientError as e:
            logging.error(f"S3 move failed: {e}")
            return False
    
    def list_files(self, prefix):
        """List files with given prefix"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            return [obj['Key'] for obj in response.get('Contents', [])]
        except ClientError as e:
            logging.error(f"S3 list failed: {e}")
            return []
    
    def generate_presigned_url(self, key, expiration=3600):
        """Generate presigned URL for secure file access"""
        try:
            response = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logging.error(f"Presigned URL generation failed: {e}")
            return None
```

#### C. File Storage Abstraction Layer

**New File: `app/services/file_service.py`**
```python
from .s3_service import S3Service
from flask import current_app
import os
import uuid
import logging

class FileService:
    def __init__(self):
        self.s3_service = S3Service()
    
    def save_post_files(self, post_id, markdown_content, html_content, title):
        """Save post markdown and HTML files to S3"""
        filename_base = f"{post_id}_{title}"
        
        # Save markdown file
        md_key = f"{current_app.config['S3_POSTS_PREFIX']}{filename_base}.md"
        self.s3_service.upload_file(
            markdown_content.encode('utf-8'),
            md_key,
            'text/markdown'
        )
        
        # Save HTML file
        html_key = f"{current_app.config['S3_POSTS_PREFIX']}{filename_base}.html"
        self.s3_service.upload_file(
            html_content.encode('utf-8'),
            html_key,
            'text/html'
        )
        
        return md_key, html_key
    
    def get_post_content(self, key):
        """Retrieve post content from S3"""
        content = self.s3_service.download_file(key)
        return content.decode('utf-8') if content else None
    
    def archive_post(self, post_key):
        """Move post to archive"""
        filename = os.path.basename(post_key)
        archive_key = f"{current_app.config['S3_ARCHIVE_PREFIX']}{filename}"
        return self.s3_service.move_file(post_key, archive_key)
    
    def delete_post(self, post_key):
        """Delete post file"""
        return self.s3_service.delete_file(post_key)
    
    # Similar methods for policy pages...
```

#### D. Route Updates

**File: `app/routes.py`**
```python
from .services.file_service import FileService

@app.route('/write_post', methods=['GET', 'POST'])
def write_post():
    # ... existing code ...
    
    if form.validate_on_submit():
        file_service = FileService()
        
        # Save files to S3 instead of local filesystem
        md_key, html_key = file_service.save_post_files(
            post_id, 
            markdown_content, 
            html_content, 
            title
        )
        
        # Update database with S3 keys instead of local paths
        post = Post(
            id=post_id,
            title=title,
            markdown_path=md_key,
            html_path=html_key,
            # ... other fields
        )
        
        # ... rest of the logic
```

### 2.3 S3 Bucket Configuration

#### A. Bucket Policy
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyPublicAccess",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::bowls-club-files",
                "arn:aws:s3:::bowls-club-files/*"
            ],
            "Condition": {
                "Bool": {
                    "aws:SecureTransport": "false"
                }
            }
        }
    ]
}
```

#### B. CORS Configuration
```json
[
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
        "AllowedOrigins": ["https://bowls-club.amazonaws.com"],
        "ExposeHeaders": []
    }
]
```

#### C. Lifecycle Policy
```json
{
    "Rules": [
        {
            "ID": "ArchiveOldFiles",
            "Status": "Enabled",
            "Transitions": [
                {
                    "Days": 30,
                    "StorageClass": "STANDARD_IA"
                },
                {
                    "Days": 90,
                    "StorageClass": "GLACIER"
                }
            ],
            "Filter": {
                "Prefix": "archive/"
            }
        }
    ]
}
```

---

## 3. Elastic Beanstalk Deployment Configuration

### 3.1 Application Structure

**Required Files:**
```
.ebextensions/
├── 01_python.config
├── 02_database.config
├── 03_https.config
└── 04_environment.config

.platform/
├── confighooks/
│   └── postdeploy/
│       └── 01_migrate_db.sh
└── nginx/
    └── conf.d/
        └── custom.conf

application.py  # Elastic Beanstalk entry point
requirements.txt
```

### 3.2 Elastic Beanstalk Configuration

#### A. Python Configuration
**File: `.ebextensions/01_python.config`**
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: application.py
  aws:elasticbeanstalk:application:environment:
    PYTHONPATH: "/var/app/current:$PYTHONPATH"
  aws:elasticbeanstalk:container:python:staticfiles:
    /static/: "app/static/"

packages:
  yum:
    postgresql-devel: []
    gcc: []
```

#### B. Database Configuration
**File: `.ebextensions/02_database.config`**
```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    DATABASE_URL: "postgresql://username:password@rds-endpoint:5432/bowls_club"
    FLASK_ENV: "production"
    SECRET_KEY: "your-secret-key-here"
    
commands:
  01_install_dependencies:
    command: "pip install -r requirements.txt"
```

#### C. HTTPS Configuration
**File: `.ebextensions/03_https.config`**
```yaml
option_settings:
  aws:elb:listener:443:
    ListenerProtocol: HTTPS
    InstancePort: 80
    InstanceProtocol: HTTP
    SSLCertificateId: arn:aws:acm:region:account:certificate/cert-id
  aws:elb:listener:80:
    ListenerProtocol: HTTP
    InstancePort: 80
    InstanceProtocol: HTTP
```

#### D. Application Entry Point
**File: `application.py`**
```python
from app import create_app
import os

application = create_app(os.getenv('FLASK_CONFIG') or 'production')

if __name__ == '__main__':
    application.run()
```

### 3.3 Database Migration Hook

**File: `.platform/confighooks/postdeploy/01_migrate_db.sh`**
```bash
#!/bin/bash
source /var/app/venv/*/bin/activate
cd /var/app/current
flask db upgrade
```

### 3.4 Environment Variables

**Required Environment Variables:**
```bash
# Database
DATABASE_URL=postgresql://username:password@rds-endpoint:5432/bowls_club

# Flask
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_S3_REGION_NAME=us-east-1
AWS_S3_BUCKET_NAME=bowls-club-files

# Email (if using SES)
MAIL_SERVER=email-smtp.us-east-1.amazonaws.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-smtp-username
MAIL_PASSWORD=your-smtp-password

# Security
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_DOMAIN=bowls-club.amazonaws.com
```

---

## 4. Security Enhancements

### 4.1 Database Security

#### A. RDS Security Group
```bash
# Allow only Elastic Beanstalk instances to access RDS
aws ec2 authorize-security-group-ingress \
    --group-id sg-rds-group \
    --protocol tcp \
    --port 5432 \
    --source-group sg-eb-group
```

#### B. Database Encryption
- Enable encryption at rest for RDS instance
- Use SSL/TLS for database connections
- Implement proper connection pooling

### 4.2 S3 Security

#### A. IAM Policy for S3 Access
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::bowls-club-files/*"
        },
        {
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::bowls-club-files"
        }
    ]
}
```

#### B. S3 Bucket Encryption
- Enable server-side encryption (SSE-S3 or SSE-KMS)
- Use versioning for file recovery
- Implement MFA delete for critical files

### 4.3 Application Security

#### A. Session Management
```python
# Use database-backed sessions or Redis
from flask_session import Session
import redis

# Redis session store
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://elasticache-endpoint:6379')
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'bowls:'

Session(app)
```

#### B. CSRF Protection
```python
# Ensure CSRF protection works with load balancer
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect(app)
app.config['WTF_CSRF_SSL_STRICT'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600
```

---

## 5. Monitoring and Logging

### 5.1 CloudWatch Integration

#### A. Application Logging
**File: `app/logging_config.py`**
```python
import logging
from logging.handlers import RotatingFileHandler
import watchtower

def setup_logging(app):
    if app.config['FLASK_ENV'] == 'production':
        # CloudWatch handler
        handler = watchtower.CloudWatchLogsHandler(
            log_group='bowls-club-app',
            stream_name='application-logs'
        )
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)
        
        # Local file handler as backup
        file_handler = RotatingFileHandler(
            'logs/bowls-club.log',
            maxBytes=10240,
            backupCount=10
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('Bowls Club application startup')
```

#### B. Custom Metrics
```python
import boto3

class CloudWatchMetrics:
    def __init__(self):
        self.cloudwatch = boto3.client('cloudwatch')
    
    def put_metric(self, metric_name, value, unit='Count'):
        self.cloudwatch.put_metric_data(
            Namespace='BowlsClub',
            MetricData=[
                {
                    'MetricName': metric_name,
                    'Value': value,
                    'Unit': unit
                }
            ]
        )
```

### 5.2 Health Check Endpoint

**File: `app/routes.py`**
```python
@app.route('/health')
def health_check():
    """Health check endpoint for load balancer"""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Check S3 connectivity
        s3_service = S3Service()
        s3_service.s3_client.head_bucket(Bucket=current_app.config['AWS_S3_BUCKET_NAME'])
        
        return {'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}, 200
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500
```

---

## 6. Performance Optimizations

### 6.1 Database Optimization

#### A. Connection Pooling
```python
# config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 0
}
```

#### B. Query Optimization
```python
# Add database indexes for frequently queried columns
class Member(db.Model):
    __table_args__ = (
        db.Index('idx_member_email', 'email'),
        db.Index('idx_member_username', 'username'),
        db.Index('idx_member_status', 'status'),
    )
```

### 6.2 Caching Strategy

#### A. Redis Cache
```python
import redis
from flask_caching import Cache

cache = Cache()

# Initialize cache
cache.init_app(app, config={
    'CACHE_TYPE': 'redis',
    'CACHE_REDIS_URL': 'redis://elasticache-endpoint:6379'
})

# Cache frequently accessed data
@cache.memoize(timeout=300)
def get_active_members():
    return Member.query.filter_by(status='Full').all()
```

#### B. CloudFront CDN
- Configure CloudFront distribution for static assets
- Set appropriate cache headers
- Use S3 as origin for file downloads

### 6.3 Session Storage

#### A. Redis Session Store
```python
# Use Redis for session storage to support multiple instances
SESSION_TYPE = 'redis'
SESSION_REDIS = redis.from_url('redis://elasticache-endpoint:6379')
SESSION_PERMANENT = False
SESSION_USE_SIGNER = True
```

---

## 7. Implementation Plan

### Phase 1: Infrastructure Setup (Week 1)
1. **AWS Account Setup**
   - Create AWS account and configure billing
   - Set up IAM roles and policies
   - Configure VPC and security groups

2. **RDS PostgreSQL Setup**
   - Create RDS PostgreSQL instance
   - Configure security groups
   - Set up database monitoring

3. **S3 Bucket Creation**
   - Create S3 bucket with proper permissions
   - Configure bucket policies and CORS
   - Set up lifecycle policies

### Phase 2: Application Migration (Week 2)
1. **Database Migration**
   - Export SQLite data
   - Create PostgreSQL schema
   - Migrate data and verify integrity

2. **File Storage Migration**
   - Implement S3 service layer
   - Migrate existing files to S3
   - Update application to use S3

3. **Configuration Updates**
   - Update config.py for AWS services
   - Set up environment variables
   - Configure logging and monitoring

### Phase 3: Elastic Beanstalk Deployment (Week 3)
1. **Application Preparation**
   - Create Elastic Beanstalk application
   - Configure deployment settings
   - Set up environment variables

2. **Initial Deployment**
   - Deploy application to staging environment
   - Run database migrations
   - Test all functionality

3. **SSL/HTTPS Configuration**
   - Configure SSL certificate
   - Set up HTTPS redirects
   - Update security headers

### Phase 4: Testing and Optimization (Week 4)
1. **Performance Testing**
   - Load testing with realistic data
   - Database performance optimization
   - CDN configuration and testing

2. **Security Testing**
   - Security scan and penetration testing
   - Review access controls
   - Audit logging verification

3. **Monitoring Setup**
   - Configure CloudWatch alarms
   - Set up log aggregation
   - Create custom dashboards

### Phase 5: Production Deployment (Week 5)
1. **Final Testing**
   - End-to-end testing
   - User acceptance testing
   - Backup and recovery testing

2. **Go-Live Preparation**
   - DNS configuration
   - Final security review
   - Deployment runbook

3. **Post-Deployment**
   - Monitor system performance
   - Address any issues
   - Document lessons learned

---

## 8. Cost Estimation

### Monthly AWS Costs (Estimated)

| Service | Configuration | Monthly Cost |
|---------|---------------|--------------|
| Elastic Beanstalk | t3.medium (2 instances) | $60 |
| RDS PostgreSQL | db.t3.micro | $25 |
| S3 Storage | 10GB + requests | $5 |
| CloudFront CDN | 100GB transfer | $10 |
| Route 53 | Hosted zone + queries | $5 |
| ElastiCache Redis | cache.t3.micro | $15 |
| **Total** | | **~$120/month** |

### Additional Considerations
- SSL certificate (free with ACM)
- CloudWatch logs and metrics (minimal cost)
- Data transfer costs (variable)
- Backup storage costs (variable)

---

## 9. Risk Assessment and Mitigation

### High-Risk Areas

1. **Data Migration**
   - **Risk**: Data loss during SQLite to PostgreSQL migration
   - **Mitigation**: Full backup, staging environment testing, rollback plan

2. **File Storage Migration**
   - **Risk**: File corruption or loss during S3 migration
   - **Mitigation**: Verify checksums, maintain local backups during transition

3. **Session Management**
   - **Risk**: User session loss during deployment
   - **Mitigation**: Gradual migration, session store backup

### Medium-Risk Areas

1. **Performance Impact**
   - **Risk**: Slower response times due to network latency
   - **Mitigation**: Caching strategy, CDN implementation, connection pooling

2. **Security Vulnerabilities**
   - **Risk**: Exposed sensitive data or unauthorized access
   - **Mitigation**: Security review, penetration testing, access controls

### Low-Risk Areas

1. **Application Code Changes**
   - **Risk**: Minimal code changes required
   - **Mitigation**: Thorough testing, gradual rollout

---

## 10. Rollback Strategy

### Immediate Rollback (< 1 hour)
1. Switch DNS back to old server
2. Restore database from backup
3. Revert file storage to local filesystem

### Partial Rollback (1-4 hours)
1. Keep AWS infrastructure
2. Restore application to previous version
3. Migrate recent data back

### Full Rollback (4+ hours)
1. Complete return to original infrastructure
2. Data synchronization from AWS to local
3. Full system restoration

---

## 11. Success Metrics

### Technical Metrics
- **Uptime**: 99.9% availability
- **Response Time**: < 2 seconds average
- **Error Rate**: < 0.1% of requests
- **Database Performance**: < 100ms query response time

### Business Metrics
- **User Adoption**: No user complaints about performance
- **Feature Functionality**: All features working as expected
- **Cost Efficiency**: Within budget constraints
- **Security**: No security incidents

---

## 12. Conclusion

This comprehensive migration plan addresses all aspects of moving the Bowls Club application to AWS with modern, scalable infrastructure. The phased approach minimizes risk while ensuring a smooth transition from the current SQLite/local file system to PostgreSQL/S3 architecture.

Key benefits of this migration:
- **Scalability**: Auto-scaling capabilities with Elastic Beanstalk
- **Reliability**: Managed database and file storage with built-in redundancy
- **Security**: Enterprise-grade security with AWS services
- **Performance**: CDN and caching for improved user experience
- **Maintainability**: Reduced operational overhead with managed services

The implementation timeline of 5 weeks allows for thorough testing and validation at each phase, ensuring a successful deployment with minimal risk to the existing application functionality.