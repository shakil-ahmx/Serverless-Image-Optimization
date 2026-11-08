import json
import boto3
import os
import logging
from urllib.parse import unquote_plus
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
import uuid

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

s3_client = boto3.client('s3')

# Supported formats
SUPPORTED_FORMATS = ['JPEG', 'PNG', 'WEBP', 'BMP', 'TIFF']
DEFAULT_QUALITY = 85
MAX_DIMENSION = 4096
THUMBNAIL_SIZE = (200, 200)

def lambda_handler(event, context):
    """
    Triggered by S3 (s3:ObjectCreated:*) on the upload bucket.
    Creates 5 variants of each image and saves them to the processed bucket.
    """
    logger.info(f"Received event: {json.dumps(event)}")

    processed_bucket = os.environ['PROCESSED_BUCKET']
    total_variants = 0

    for record in event.get('Records', []):
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        logger.info(f"Processing image: {key} from bucket: {bucket}")

        # Download the original image
        response = s3_client.get_object(Bucket=bucket, Key=key)
        image_data = response['Body'].read()

        # Create variants (non-image files are skipped, not retried)
        try:
            processed_images = process_image(image_data, key)
        except UnidentifiedImageError:
            logger.warning(f"Skipping {key}: not a valid image file")
            continue

        # Upload variants to the processed bucket
        for processed_image in processed_images:
            output_key = processed_image['key']
            logger.info(f"Uploading processed image: {output_key}")

            s3_client.put_object(
                Bucket=processed_bucket,
                Key=output_key,
                Body=processed_image['data'],
                ContentType=processed_image['content_type'],
                Metadata={
                    'original-key': key.encode('ascii', 'replace').decode('ascii'),
                    'processed-by': 'lambda-image-processor'
                }
            )

        total_variants += len(processed_images)
        logger.info(f"Successfully processed {len(processed_images)} variants of {key}")

    # Errors are NOT swallowed: an exception marks the invocation as failed
    # (visible in CloudWatch metrics, and S3 retries async invocations).
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Image processing complete',
            'processed_images': total_variants
        })
    }


def process_image(image_data, original_key):
    """
    Process the image: create compressed versions and convert formats.
    
    Args:
        image_data: Raw image data
        original_key: Original S3 key
        
    Returns:
        List of processed image dictionaries
    """
    processed_images = []
    
    try:
        # Open the image
        image = Image.open(BytesIO(image_data))
        original_format = image.format or 'JPEG'

        # Respect camera rotation (EXIF) so phone photos are not sideways
        image = ImageOps.exif_transpose(image)
        
        # Convert RGBA to RGB for JPEG compatibility
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Get dimensions
        width, height = image.size
        
        logger.info(f"Original image: {width}x{height}, format: {original_format}")
        
        # Resize if image is too large
        if width > MAX_DIMENSION or height > MAX_DIMENSION:
            ratio = min(MAX_DIMENSION / width, MAX_DIMENSION / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"Resized to: {new_width}x{new_height}")
        
        # Generate base filename
        base_name = os.path.splitext(original_key)[0]
        unique_id = str(uuid.uuid4())[:8]
        
        # Create multiple variants
        variants = [
            {'format': 'JPEG', 'quality': 85, 'suffix': 'compressed'},
            {'format': 'JPEG', 'quality': 60, 'suffix': 'low'},
            {'format': 'WEBP', 'quality': 85, 'suffix': 'webp'},
            {'format': 'PNG', 'quality': None, 'suffix': 'png'}
        ]
        
        for variant in variants:
            output = BytesIO()
            save_format = variant['format']
            
            if variant['quality']:
                image.save(output, format=save_format, quality=variant['quality'], optimize=True)
            else:
               image.save(output, format=save_format, compress_level=6)
            
            output.seek(0)
            
            # Generate output key
            extension = save_format.lower()
            if extension == 'jpeg':
                extension = 'jpg'
            
            output_key = f"{base_name}_{variant['suffix']}_{unique_id}.{extension}"
            
            # Determine content type
            content_type_map = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'WEBP': 'image/webp'
            }
            content_type = content_type_map.get(save_format, 'image/jpeg')
            
            processed_images.append({
                'key': output_key,
                'data': output.getvalue(),
                'content_type': content_type,
                'format': save_format,
                'quality': variant['quality']
            })
            
            logger.info(f"Created variant: {output_key} ({save_format}, quality: {variant['quality']})")
        
        # Create thumbnail
        thumbnail = image.copy()
        thumbnail.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        thumb_output = BytesIO()
        thumbnail.save(thumb_output, format='JPEG', quality=80, optimize=True)
        thumb_output.seek(0)
        
        processed_images.append({
            'key': f"{base_name}_thumbnail_{unique_id}.jpg",
            'data': thumb_output.getvalue(),
            'content_type': 'image/jpeg',
            'format': 'JPEG',
            'quality': 80
        })
        
        logger.info(f"Created thumbnail: {base_name}_thumbnail_{unique_id}.jpg")
        
        return processed_images
        
    except UnidentifiedImageError:
        raise
    except Exception as e:
        logger.error(f"Error in process_image: {str(e)}", exc_info=True)
        raise
