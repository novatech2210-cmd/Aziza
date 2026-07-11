import { AllExceptionsFilter } from './all-exceptions.filter';
import { HttpException, HttpStatus } from '@nestjs/common';

describe('AllExceptionsFilter', () => {
  let filter: AllExceptionsFilter;
  let mockResponse: any;
  let mockRequest: any;
  let mockHost: any;

  beforeEach(() => {
    filter = new AllExceptionsFilter();
    mockResponse = { status: jest.fn().mockReturnThis(), json: jest.fn() };
    mockRequest = { headers: {} };
    mockHost = {
      switchToHttp: () => ({
        getResponse: () => mockResponse,
        getRequest: () => mockRequest,
      }),
    };
  });

  it('should handle HttpException with status and message', () => {
    const exception = new HttpException('Not found', HttpStatus.NOT_FOUND);
    filter.catch(exception, mockHost as any);
    expect(mockResponse.status).toHaveBeenCalledWith(404);
    expect(mockResponse.json).toHaveBeenCalledWith(
      expect.objectContaining({ statusCode: 404, message: 'Not found' }),
    );
  });

  it('should handle generic Error as 500', () => {
    filter.catch(new Error('something broke'), mockHost as any);
    expect(mockResponse.status).toHaveBeenCalledWith(500);
    expect(mockResponse.json).toHaveBeenCalledWith(
      expect.objectContaining({ statusCode: 500, message: 'Internal server error' }),
    );
  });

  it('should include correlationId from headers', () => {
    mockRequest.headers['x-correlation-id'] = 'req-123';
    filter.catch(new Error('fail'), mockHost as any);
    expect(mockResponse.json).toHaveBeenCalledWith(
      expect.objectContaining({ correlationId: 'req-123' }),
    );
  });

  it('should include timestamp', () => {
    filter.catch(new Error('fail'), mockHost as any);
    const body = mockResponse.json.mock.calls[0][0];
    expect(body.timestamp).toBeDefined();
    expect(new Date(body.timestamp).getTime()).not.toBeNaN();
  });

  it('should handle HttpException with object response', () => {
    const exception = new HttpException(
      { message: ['email is invalid'], error: 'Bad Request' },
      HttpStatus.BAD_REQUEST,
    );
    filter.catch(exception, mockHost as any);
    expect(mockResponse.status).toHaveBeenCalledWith(400);
  });
});
